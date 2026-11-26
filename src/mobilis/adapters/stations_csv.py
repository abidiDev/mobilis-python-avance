"""Lecture du référentiel stations.csv (export d'un ancien outil Windows).

Le fichier est lu tel quel : encodage CP1252, séparateur `;`, décimales à
virgule. Chaque valeur corrigée ou écartée est signalée ; la lecture ne
s'arrête jamais à la première anomalie.
"""

import csv
import re
from collections.abc import Callable, Iterator
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from mobilis.domain.anomalies import Anomalie, NiveauAnomalie, SignalerAnomalie
from mobilis.domain.models import Station, StatutStation

ENCODAGE = "cp1252"
COLONNES = (
    "Code station",
    "Nom",
    "Commune",
    "Capacité",
    "Latitude",
    "Longitude",
    "Statut",
    "Mise en service",
)
_CODE = re.compile(r"MB-\d{4}")
_STATUTS = {
    "en service": StatutStation.EN_SERVICE,
    "hors service": StatutStation.HORS_SERVICE,
    "hs": StatutStation.HORS_SERVICE,
    "fermee": StatutStation.FERMEE,
    "fermée": StatutStation.FERMEE,
}
_CAPACITE_INCONNUE = {"", "nc", "n/c", "?"}

Signal = Callable[[str, str, NiveauAnomalie, str, str], None]


class LigneRejetee(ValueError):
    """Valeur obligatoire illisible : la ligne entière est écartée."""


def normaliser_statut(brut: str) -> StatutStation:
    """`'En service '`, `'EN SERVICE'`, `'en_service'` → EN_SERVICE ; `'HS'` → HORS_SERVICE."""
    cle = brut.strip().lower().replace("_", " ")
    try:
        return _STATUTS[cle]
    except KeyError:
        raise LigneRejetee(f"statut inconnu {brut!r}") from None


def lire_date(brut: str, signal: Signal) -> date:
    valeur = brut.strip()
    try:
        return datetime.strptime(valeur, "%d/%m/%Y").date()
    except ValueError:
        pass
    try:
        jour = date.fromisoformat(valeur)
    except ValueError:
        raise LigneRejetee(f"date de mise en service illisible {brut!r}") from None
    signal(
        "Mise en service",
        "DATE_FORMAT_ISO",
        NiveauAnomalie.INFO,
        brut,
        "Lue au format AAAA-MM-JJ",
    )
    return jour


def lire_capacite(brut: str, signal: Signal) -> int | None:
    valeur = brut.strip()
    if valeur.lower() in _CAPACITE_INCONNUE:
        signal(
            "Capacité",
            "CAPACITE_INCONNUE",
            NiveauAnomalie.ALERTE,
            brut,
            "Capacité inconnue (None) : station non exploitable",
        )
        return None
    try:
        capacite = int(valeur)
    except ValueError:
        capacite = 0
    if capacite <= 0:
        signal(
            "Capacité",
            "CAPACITE_INVALIDE",
            NiveauAnomalie.ALERTE,
            brut,
            "Capacité inconnue (None) : station non exploitable",
        )
        return None
    if valeur != brut:
        signal("Capacité", "ESPACES_SUPERFLUS", NiveauAnomalie.INFO, brut, "Espaces retirés")
    return capacite


def _decimal(brut: str) -> Decimal | None:
    try:
        valeur = Decimal(brut.strip().replace(",", "."))
        return valeur if valeur.is_finite() else None
    except InvalidOperation:
        return None


def lire_coordonnees(
    brut_lat: str, brut_lon: str, signal: Signal
) -> tuple[Decimal | None, Decimal | None]:
    valeur = f"{brut_lat};{brut_lon}"
    if not brut_lat.strip() and not brut_lon.strip():
        signal(
            "Latitude/Longitude",
            "COORDONNEES_ABSENTES",
            NiveauAnomalie.ALERTE,
            valeur,
            "Coordonnées inconnues (None)",
        )
        return None, None
    latitude, longitude = _decimal(brut_lat), _decimal(brut_lon)
    if (
        latitude is None
        or longitude is None
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        signal(
            "Latitude/Longitude",
            "COORDONNEES_INVALIDES",
            NiveauAnomalie.ALERTE,
            valeur,
            "Coordonnées inconnues (None)",
        )
        return None, None
    # Réseau situé vers 45,7° N et 4,8° E : une latitude inférieure à la
    # longitude ne peut provenir que d'une inversion des deux colonnes.
    if latitude < longitude:
        signal(
            "Latitude/Longitude",
            "COORDONNEES_INVERSEES",
            NiveauAnomalie.ALERTE,
            valeur,
            "Colonnes permutées puis conservées",
        )
        return longitude, latitude
    return latitude, longitude


def _texte(brut: str, champ: str, signal: Signal) -> str:
    valeur = brut.strip()
    if not valeur:
        raise LigneRejetee(f"{champ} vide")
    if valeur != brut:
        signal(champ, "ESPACES_SUPERFLUS", NiveauAnomalie.INFO, brut, "Espaces retirés")
    return valeur


def convertir_ligne(ligne: dict[str, str], signal: Signal) -> Station:
    """Convertir une ligne brute en Station ; lève LigneRejetee si c'est impossible."""
    code = ligne["Code station"].strip()
    if not _CODE.fullmatch(code):
        raise LigneRejetee(f"code station invalide {ligne['Code station']!r}")
    statut_brut = ligne["Statut"]
    statut = normaliser_statut(statut_brut)
    if statut_brut != statut.value:
        signal(
            "Statut",
            "STATUT_NON_NORMALISE",
            NiveauAnomalie.INFO,
            statut_brut,
            f"Normalisé en « {statut.value} »",
        )
    latitude, longitude = lire_coordonnees(ligne["Latitude"], ligne["Longitude"], signal)
    try:
        return Station(
            code=code,
            nom=_texte(ligne["Nom"], "Nom", signal),
            commune=_texte(ligne["Commune"], "Commune", signal),
            capacite=lire_capacite(ligne["Capacité"], signal),
            latitude=latitude,
            longitude=longitude,
            statut=statut,
            mise_en_service=lire_date(ligne["Mise en service"], signal),
        )
    except (ValueError, TypeError) as exc:
        if isinstance(exc, LigneRejetee):
            raise
        raise LigneRejetee(str(exc)) from exc


class LecteurStationsCsv:
    """Implémentation de SourceStations : une Station par ligne valide.

    Les codes répétés ne sont pas fusionnés ici : chaque version est émise,
    le service `stations` décide laquelle constitue le référentiel.
    """

    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin

    def lire(self, signaler: SignalerAnomalie) -> Iterator[Station]:
        source = self.chemin.name
        with self.chemin.open(encoding=ENCODAGE, newline="") as flux:
            lecteur = csv.DictReader(flux, delimiter=";")
            if lecteur.fieldnames is None or tuple(lecteur.fieldnames) != COLONNES:
                raise ValueError(f"En-têtes inattendus dans {source} : {lecteur.fieldnames!r}")
            for brut in lecteur:
                numero = lecteur.line_num
                identifiant = (brut.get("Code station") or "").strip()

                def signal(
                    champ: str,
                    code: str,
                    niveau: NiveauAnomalie,
                    valeur: str,
                    decision: str,
                    numero: int = numero,
                    identifiant: str = identifiant,
                ) -> None:
                    signaler(
                        Anomalie(source, numero, identifiant, champ, code, niveau, valeur, decision)
                    )

                if None in brut or any(v is None for v in brut.values()):
                    signal(
                        "ligne",
                        "COLONNES_INVALIDES",
                        NiveauAnomalie.ERREUR,
                        str(brut),
                        "Ligne écartée",
                    )
                    continue
                try:
                    yield convertir_ligne(brut, signal)
                except LigneRejetee as exc:
                    signal(
                        "ligne", "LIGNE_REJETEE", NiveauAnomalie.ERREUR, str(exc), "Ligne écartée"
                    )
