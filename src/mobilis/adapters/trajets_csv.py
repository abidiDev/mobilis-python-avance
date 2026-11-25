"""Lecture en flux des trajets CSV.gz, normalisation et dédoublonnage sur disque."""

import csv
import gzip
import json
import sqlite3
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
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
        date_obj = datetime.fromisoformat(valeur)
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
                signaler,
                source,
                ligne,
                identifiant,
                champ,
                "HEURE_LOCALE_AMBIGUE",
                NiveauAnomalie.ALERTE,
                valeur,
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
            signaler,
            source,
            ligne,
            id_trajet,
            "ligne",
            "CHAMP_OBLIGATOIRE_ABSENT",
            NiveauAnomalie.ERREUR,
            str({champ: row[champ] for champ in obligatoire}),
            "Écarter la ligne (modèle incomplet)",
        )
        return None
    try:
        type_velo = TypeVelo(row["type_velo"].strip().lower())
        debut = convertir_date(row["debut"], signaler, source, ligne, id_trajet, "debut")
        fin = (
            convertir_date(row["fin"], signaler, source, ligne, id_trajet, "fin")
            if row["fin"].strip()
            else None
        )
    except ValueError as exc:
        _signaler(
            signaler,
            source,
            ligne,
            id_trajet,
            "date/type_velo",
            "DONNEE_INVALIDE",
            NiveauAnomalie.ERREUR,
            str(exc),
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
                signaler,
                source,
                ligne,
                id_trajet,
                "distance_m",
                "DISTANCE_INVALIDE",
                NiveauAnomalie.ALERTE,
                row["distance_m"],
                "Conserver le trajet avec distance inconnue",
            )
            distance = None
    arrivee = row["station_arrivee"].strip() or None
    if (fin is None) != (arrivee is None):
        _signaler(
            signaler,
            source,
            ligne,
            id_trajet,
            "fin/station_arrivee",
            "RETOUR_PARTIEL",
            NiveauAnomalie.ALERTE,
            f"fin={row['fin']}; station={row['station_arrivee']}",
            "Conserver et signaler, sans appliquer de pénalité ici",
        )
    if fin is not None and fin < debut:
        _signaler(
            signaler,
            source,
            ligne,
            id_trajet,
            "fin",
            "DUREE_NEGATIVE",
            NiveauAnomalie.ALERTE,
            row["fin"],
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


# --- Pipeline de générateurs ------------------------------------------------
# Chaque étape consomme l'itérateur de la précédente et produit le sien :
#   lire_lignes_brutes -> normaliser_lignes -> dedoublonner
# Une seule ligne circule à la fois dans toute la chaîne (évaluation paresseuse).


@dataclass(frozen=True, slots=True)
class LigneBrute:
    """Ligne CSV telle que lue, avec son numéro physique (en-tête = 1)."""

    numero: int
    valeurs: dict[str, str]


@dataclass(frozen=True, slots=True)
class TrajetLu:
    """Trajet normalisé accompagné de sa provenance, pour le dédoublonnage."""

    numero: int
    brut: LigneBrute
    trajet: Trajet


def lire_lignes_brutes(chemin: Path, signaler: SignalerAnomalie) -> Iterator[LigneBrute]:
    """Étape 1 : décompresser et découper le CSV, sans interpréter les valeurs."""
    source = chemin.name
    with gzip.open(chemin, mode="rt", encoding="utf-8-sig", newline="") as flux:
        lecteur = csv.DictReader(flux)
        if lecteur.fieldnames is None or tuple(lecteur.fieldnames) != _COLONNES:
            raise ValueError(f"En-têtes CSV inattendus : {lecteur.fieldnames!r}")
        for brut in lecteur:
            ligne = lecteur.line_num
            if None in brut or any(not isinstance(v, str) for v in brut.values()):
                _signaler(
                    signaler,
                    source,
                    ligne,
                    "",
                    "ligne",
                    "COLONNES_INVALIDES",
                    NiveauAnomalie.ERREUR,
                    str(brut),
                    "Écarter cette ligne",
                )
                continue
            yield LigneBrute(ligne, {str(k): str(v) for k, v in brut.items()})


def normaliser_lignes(
    lignes: Iterable[LigneBrute], signaler: SignalerAnomalie, source: str
) -> Iterator[TrajetLu]:
    """Étape 2 : convertir chaque ligne en Trajet ; les lignes invalides sont signalées."""
    for ligne in lignes:
        trajet = _normaliser(ligne.valeurs, signaler, source, ligne.numero)
        if trajet is not None:
            yield TrajetLu(ligne.numero, ligne, trajet)


def _empreinte(lu: TrajetLu) -> str:
    return json.dumps([lu.brut.valeurs[k] for k in _COLONNES], ensure_ascii=False)


class IndexDedoublonnage:
    """Index des trajet_id déjà émis, stocké dans un SQLite temporaire sur disque.

    Un `set` en RAM grossirait avec le fichier ; le disque garde la mémoire bornée.
    """

    def __init__(self, dossier: Path) -> None:
        self.chemin = dossier / "ids.sqlite"
        self._db = sqlite3.connect(str(self.chemin))
        self._db.execute("CREATE TABLE vus (trajet_id TEXT PRIMARY KEY, empreinte TEXT NOT NULL)")

    def ajouter(self, trajet_id: str, empreinte: str) -> str | None:
        """Enregistrer l'ID ; retourner l'empreinte déjà connue s'il existait."""
        resultat = self._db.execute(
            "INSERT OR IGNORE INTO vus VALUES (?, ?)", (trajet_id, empreinte)
        )
        if resultat.rowcount == 1:
            return None
        ancien = self._db.execute(
            "SELECT empreinte FROM vus WHERE trajet_id = ?", (trajet_id,)
        ).fetchone()
        return str(ancien[0])

    def fermer(self) -> None:
        self._db.close()


def dedoublonner(
    trajets: Iterable[TrajetLu],
    index: IndexDedoublonnage,
    signaler: SignalerAnomalie,
    source: str,
) -> Iterator[Trajet]:
    """Étape 3 : émettre chaque trajet_id une seule fois (première ligne valide)."""
    for lu in trajets:
        empreinte = _empreinte(lu)
        ancienne = index.ajouter(lu.trajet.trajet_id, empreinte)
        if ancienne is None:
            yield lu.trajet
            continue
        identique = ancienne == empreinte
        _signaler(
            signaler,
            source,
            lu.numero,
            lu.trajet.trajet_id,
            "trajet_id",
            "DOUBLON_IDENTIQUE" if identique else "ID_EN_CONFLIT",
            NiveauAnomalie.INFO if identique else NiveauAnomalie.ERREUR,
            lu.trajet.trajet_id,
            "Conserver la première ligne valide, écarter la répétition",
        )


class LecteurTrajetsGzip:
    """Implémentation de SourceTrajets : assemble les trois étapes du pipeline.

    Un identifiant est émis au plus une fois. Les doublons exacts sont signalés ;
    les identifiants réutilisés avec un contenu différent sont signalés aussi.
    Les données brutes ne sont jamais modifiées.
    """

    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.taille_index_octets: int | None = None

    def lire(self, signaler: SignalerAnomalie) -> Iterator[Trajet]:
        """Lire et fournir chaque trajet valide sans charger le CSV entier en RAM."""
        source = self.chemin.name
        self.taille_index_octets = None
        with tempfile.TemporaryDirectory(prefix="mobilis-dedup-") as tmp:
            index = IndexDedoublonnage(Path(tmp))
            try:
                lignes = lire_lignes_brutes(self.chemin, signaler)
                normalises = normaliser_lignes(lignes, signaler, source)
                yield from dedoublonner(normalises, index, signaler, source)
                # Taille du fichier SQLite avant la suppression du répertoire temporaire.
                self.taille_index_octets = index.chemin.stat().st_size
            finally:
                index.fermer()
