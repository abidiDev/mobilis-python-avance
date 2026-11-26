"""Structures métier partagées par les adapters et les services Mobilis.

Ces types représentent des données *normalisées*. Les adapters signalent
les valeurs brutes invalides avant de construire ces objets.
La validation métier détaillée appartient aux tickets des modules concernés.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class StatutStation(StrEnum):
    """États reconnus dans l'export stations.csv après normalisation."""

    EN_SERVICE = "en_service"
    HORS_SERVICE = "hors_service"
    FERMEE = "fermee"


class TypeVelo(StrEnum):
    """Types effectivement présents dans le CSV des trajets."""

    MECANIQUE = "mecanique"
    ELECTRIQUE = "electrique"


class FormuleAbonnement(StrEnum):
    """Formules des abonnements et de la grille tarifaire.

    OCCASIONNEL existe dans les tarifs, même sans fiche JSONL d'abonnement.
    La décision d'appliquer cette formule reste une règle de facturation.
    """

    ANNUEL = "annuel"
    MENSUEL = "mensuel"
    SOLIDAIRE = "solidaire"
    OCCASIONNEL = "occasionnel"


@dataclass(frozen=True, slots=True)
class Station:
    """Station de référence, immuable et validée à la construction.

    Les invariants vérifiés ici valent pour toute station, quelle que soit sa
    source. Le format des codes de l'export (`MB-0001`) et les corrections
    de données brutes relèvent du lecteur CSV ; la résolution des codes
    répétés relève du service `stations`.
    """

    code: str
    nom: str
    commune: str
    capacite: int | None
    latitude: Decimal | None
    longitude: Decimal | None
    statut: StatutStation
    mise_en_service: date

    def __post_init__(self) -> None:
        for champ in ("code", "nom", "commune"):
            valeur = getattr(self, champ)
            if not valeur or valeur != valeur.strip():
                raise ValueError(f"{champ} vide ou entouré d'espaces : {valeur!r}")
        if self.capacite is not None and self.capacite <= 0:
            raise ValueError(f"capacité non positive : {self.capacite}")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude et longitude doivent être connues ensemble")
        if self.latitude is not None and (
            not self.latitude.is_finite() or not -90 <= self.latitude <= 90
        ):
            raise ValueError(f"latitude hors limites : {self.latitude}")
        if self.longitude is not None and (
            not self.longitude.is_finite() or not -180 <= self.longitude <= 180
        ):
            raise ValueError(f"longitude hors limites : {self.longitude}")
        if not isinstance(self.statut, StatutStation):
            raise TypeError(f"statut inattendu : {self.statut!r}")

    @property
    def en_service(self) -> bool:
        return self.statut is StatutStation.EN_SERVICE


@dataclass(frozen=True, slots=True)
class Trajet:
    """Trajet normalisé ; début/fin sont des datetimes avec fuseau (UTC cible).

    Une fin absente n'implique pas automatiquement un type de facturation.
    """

    trajet_id: str
    abonne_id: str | None
    velo_id: str
    type_velo: TypeVelo
    station_depart: str
    debut: datetime
    station_arrivee: str | None
    fin: datetime | None
    distance_m: int | None


@dataclass(frozen=True, slots=True)
class PeriodeAbonnement:
    """Une période d'un historique : plusieurs lignes par abonné sont permises."""

    id: str
    formule: FormuleAbonnement
    debut: date
    fin: date | None
    commune: str


@dataclass(frozen=True, slots=True)
class TarifFormule:
    """Paramètres d'une formule, montants représentés exclusivement en Decimal."""

    minutes_incluses: int
    tranche_minutes: int
    prix_tranche: Decimal
    supplement_electrique_tranche: Decimal
    frais_deblocage: Decimal
    plafond_jour: Decimal | None


@dataclass(frozen=True, slots=True)
class GrilleTarifaire:
    """Grille applicable à partir d'une date donnée."""

    en_vigueur_du: date
    formules: Mapping[FormuleAbonnement, TarifFormule]


@dataclass(frozen=True, slots=True)
class ConfigurationTarifaire:
    """Configuration globale : grilles historiques et pénalité d'absence de retour."""

    devise: str
    penalite_non_restitution: Decimal
    seuil_non_restitution_heures: int
    grilles: tuple[GrilleTarifaire, ...]
