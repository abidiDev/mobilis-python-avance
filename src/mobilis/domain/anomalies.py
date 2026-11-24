"""Contrat d'anomalies commun aux lecteurs et aux règles métier.

Une anomalie observée ne signifie pas systématiquement un rejet de ligne.
La politique métier appartient au service concerné.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class NiveauAnomalie(StrEnum):
    """Niveaux convenus pour le journal d'audit."""

    ERREUR = "erreur"
    ALERTE = "alerte"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class Anomalie:
    """Signalement avec un emplacement explicite dans la source.

    ligne est un numéro physique de ligne CSV/JSONL (à partir de 1).
    Une source sans numéro de ligne, par exemple HTTP, utilise None.
    """

    fichier_source: str
    ligne: int | None
    identifiant: str
    champ: str
    code_anomalie: str
    niveau: NiveauAnomalie
    valeur_observee: str
    traitement_propose: str


SignalerAnomalie = Callable[[Anomalie], None]


class CollecteurAnomalies:
    """Collecteur local et explicite, sans état global caché."""

    def __init__(self) -> None:
        self._elements: list[Anomalie] = []

    def signaler(self, anomalie: Anomalie) -> None:
        self._elements.append(anomalie)

    @property
    def elements(self) -> tuple[Anomalie, ...]:
        """Instantané immuable des anomalies déjà signalées."""
        return tuple(self._elements)
