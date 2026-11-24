"""Lecture en flux des trajets CSV.gz, normalisation et dédoublonnage sur disque."""

import csv
import gzip
import json
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mobilis.domain.anomalies import Anomalie, NiveauAnomalie, SignalerAnomalie
from mobilis.domain.models import Trajet, TypeVelo

_COLONNES = (
    "trajet_id",
    "abonne_id",
    "velo_id",
    "type_velo",
    "station_depart",
    "debut",
    "station_arrivee",
    "fin",
    "distance_m",
)
_PARIS = ZoneInfo("Europe/Paris")


def _signaler(
    signaler: SignalerAnomalie,
    source: str,
    ligne: int,
    identifiant: str,
    champ: str,
    code: str,
    niveau: NiveauAnomalie,
    valeur: str,
    decision: str,
) -> None:
    signaler(
        Anomalie(
            fichier_source=source,
            ligne=ligne,
            identifiant=identifiant,
            champ=champ,
            code_anomalie=code,
            niveau=niveau,
            valeur_observee=valeur,
            traitement_propose=decision,
        )
    )


def convertir_date(
    brut: str,
    signaler: SignalerAnomalie,
    source: str,
    ligne: int,
    identifiant: str,
    champ: str,
) -> datetime:
    """Convertir ISO 8601, UTC Z ou date française locale en instant UTC.

    Convention à confirmer : en octobre, une heure locale ambiguë est
    interprétée avec fold=0 (première occurrence), puis signalée.
    Une heure locale inexistante au printemps est rejetée.
    """
    valeur = brut.strip()
    if not valeur:
        raise ValueError("date absente")
    try:
        date_obj = datetime.fromisoformat(valeur.replace("Z", "+00:00"))
    except ValueError:
        date_obj = datetime.strptime(valeur, "%d/%m/%Y %H:%M:%S")
    if date_obj.tzinfo is None:
        date_obj = date_obj.replace(tzinfo=_PARIS, fold=0)
        retour = date_obj.astimezone(UTC).astimezone(_PARIS)
        if retour.replace(tzinfo=None) != date_obj.replace(tzinfo=None):
            raise ValueError("heure locale inexistante (changement d'heure)")
        alternative = date_obj.replace(fold=1)
        if date_obj.utcoffset() != alternative.utcoffset():
            _signaler(
                signaler, source, ligne, identifiant, champ,
                "HEURE_LOCALE_AMBIGUE", NiveauAnomalie.ALERTE, valeur,
                "Première occurrence (fold=0), à valider en binôme",
            )
    return date_obj.astimezone(UTC)


def _normaliser(
    row: dict[str, str],
    signaler: SignalerAnomalie,
    source: str,
    ligne: int,
) -> Trajet | None:
    id_trajet = row["trajet_id"].strip()
    obligatoire = ("trajet_id", "velo_id", "type_velo", "station_depart", "debut")
    if not all(row[champ].strip() for champ in obligatoire):
        _signaler(
            signaler, source, ligne, id_trajet, "ligne",
            "CHAMP_OBLIGATOIRE_ABSENT", NiveauAnomalie.ERREUR,
            str({champ: row[champ] for champ in obligatoire}),
            "Écarter la ligne (modèle incomplet)",
        )
        return None
    try:
        type_velo = TypeVelo(row["type_velo"].strip().lower())
        debut = convertir_date(
            row["debut"], signaler, source, ligne, id_trajet, "debut"
        )
        fin = (
            convertir_date(row["fin"], signaler, source, ligne, id_trajet, "fin")
            if row["fin"].strip()
            else None
        )
    except ValueError as exc:
        _signaler(
            signaler, source, ligne, id_trajet, "date/type_velo",
            "DONNEE_INVALIDE", NiveauAnomalie.ERREUR, str(exc),
            "Écarter la ligne (valeur non interprétable)",
        )
        return None

    distance: int | None = None
    if row["distance_m"].strip():
        try:
            distance = int(row["distance_m"])
            if distance < 0:
                raise ValueError("distance négative")
        except ValueError:
            _signaler(
                signaler, source, ligne, id_trajet, "distance_m",
                "DISTANCE_INVALIDE", NiveauAnomalie.ALERTE,
                row["distance_m"], "Conserver le trajet avec distance inconnue",
            )
            distance = None
    arrivee = row["station_arrivee"].strip() or None
    if (fin is None) != (arrivee is None):
        _signaler(
            signaler, source, ligne, id_trajet, "fin/station_arrivee",
            "RETOUR_PARTIEL", NiveauAnomalie.ALERTE,
            f"fin={row['fin']}; station={row['station_arrivee']}",
            "Conserver et signaler, sans appliquer de pénalité ici",
        )
    if fin is not None and fin < debut:
        _signaler(
            signaler, source, ligne, id_trajet, "fin",
            "DUREE_NEGATIVE", NiveauAnomalie.ALERTE, row["fin"],
            "Conserver l'instant brut normalisé ; exclure les durées négatives des durées",
        )
    return Trajet(
        trajet_id=id_trajet,
        abonne_id=row["abonne_id"].strip() or None,
        velo_id=row["velo_id"].strip(),
        type_velo=type_velo,
        station_depart=row["station_depart"].strip(),
        debut=debut,
        station_arrivee=arrivee,
        fin=fin,
        distance_m=distance,
    )


class LecteurTrajetsGzip:
    """Implémentation de SourceTrajets avec index SQLite temporaire sur disque.

    Un identifiant est émis au plus une fois. Les doublons exacts sont signalés ;
    les identifiants réutilisés avec un contenu différent sont signalés aussi.
    Les données brutes ne sont jamais modifiées.
    """

    def __init__(self, chemin: Path):
        self.chemin = chemin

    def lire(self, signaler: SignalerAnomalie) -> Iterator[Trajet]:
        """Lire et fournir chaque trajet valide sans charger le CSV entier en RAM."""
        source = self.chemin.name
        with tempfile.TemporaryDirectory(prefix="mobilis-dedup-") as tmp:
            with closing(sqlite3.connect(str(Path(tmp) / "ids.sqlite"))) as db:
                db.execute(
                    "CREATE TABLE vus (trajet_id TEXT PRIMARY KEY, empreinte TEXT NOT NULL)"
                )
                with gzip.open(self.chemin, mode="rt", encoding="utf-8-sig", newline="") as flux:
                    lecteur = csv.DictReader(flux)
                    if lecteur.fieldnames is None or tuple(lecteur.fieldnames) != _COLONNES:
                        raise ValueError(
                            f"En-têtes CSV inattendus : {lecteur.fieldnames!r}"
                        )
                    for brut in lecteur:
                        ligne = lecteur.line_num
                        if None in brut or any(not isinstance(v, str) for v in brut.values()):
                            _signaler(
                                signaler, source, ligne, "", "ligne",
                                "COLONNES_INVALIDES", NiveauAnomalie.ERREUR,
                                str(brut), "Écarter cette ligne",
                            )
                            continue
                        row = {str(k): str(v) for k, v in brut.items()}
                        trajet = _normaliser(row, signaler, source, ligne)
                        if trajet is None:
                            continue
                        empreinte = json.dumps(
                            [row[k] for k in _COLONNES], ensure_ascii=False
                        )
                        result = db.execute(
                            "INSERT OR IGNORE INTO vus VALUES (?, ?)",
                            (trajet.trajet_id, empreinte),
                        )
                        if result.rowcount == 0:
                            ancien = db.execute(
                                "SELECT empreinte FROM vus WHERE trajet_id = ?",
                                (trajet.trajet_id,),
                            ).fetchone()
                            identique = ancien is not None and ancien[0] == empreinte
                            _signaler(
                                signaler, source, ligne, trajet.trajet_id, "trajet_id",
                                "DOUBLON_IDENTIQUE" if identique else "ID_EN_CONFLIT",
                                NiveauAnomalie.INFO if identique else NiveauAnomalie.ERREUR,
                                trajet.trajet_id,
                                "Conserver la première ligne valide, écarter la répétition",
                            )
                            continue
                        yield trajet
