"""Ports de lecture partagés entre l'orchestration et les adaptateurs.

Les adapters concrets peuvent être configurés avec un Path au constructeur.
Les services reçoivent les objets métier et ne dépendent pas de ces ports.
Les contrats du serveur HTTP et de tarification seront fixés sur les specs R1-R12
et serveur_bornes.py, sans préjuger de leurs formes ici.
"""

from collections.abc import Iterator
from typing import Protocol

from mobilis.domain.anomalies import SignalerAnomalie
from mobilis.domain.models import (
    ConfigurationTarifaire,
    PeriodeAbonnement,
    Station,
    Trajet,
)


class SourceStations(Protocol):
    """Fournit les stations sans écraser les versions d'un même code."""

    def lire(self, signaler: SignalerAnomalie) -> Iterator[Station]: ...


class SourceTrajets(Protocol):
    """Fournit les trajets en flux, sans chargement complet du CSV.gz."""

    def lire(self, signaler: SignalerAnomalie) -> Iterator[Trajet]: ...


class SourceAbonnements(Protocol):
    """Fournit toutes les périodes, même si un abonné apparaît plusieurs fois."""

    def lire(self, signaler: SignalerAnomalie) -> Iterator[PeriodeAbonnement]: ...


class SourceTarifs(Protocol):
    """Fournit les grilles tarifaires avec des valeurs Decimal."""

    def lire(self, signaler: SignalerAnomalie) -> ConfigurationTarifaire: ...
