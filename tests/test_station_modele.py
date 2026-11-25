"""Tests T-04 : invariants de la dataclass Station."""

from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mobilis.domain.models import Station, StatutStation


def _station(**champs: Any) -> Station:
    valeurs: dict[str, Any] = {
        "code": "MB-0001",
        "nom": "Hôpital Lamartine",
        "commune": "Valmont",
        "capacite": 37,
        "latitude": Decimal("45.78525"),
        "longitude": Decimal("4.87212"),
        "statut": StatutStation.EN_SERVICE,
        "mise_en_service": date(2017, 12, 16),
    }
    valeurs.update(champs)
    return Station(**valeurs)


def test_station_valide_et_immuable() -> None:
    station = _station()
    assert station.en_service
    with pytest.raises(FrozenInstanceError):
        station.capacite = 10  # type: ignore[misc]


def test_valeurs_inconnues_autorisees() -> None:
    station = _station(capacite=None, latitude=None, longitude=None)
    assert station.capacite is None and station.latitude is None


@pytest.mark.parametrize(
    "champs",
    [
        {"code": ""},
        {"nom": "Rue des Forges  "},
        {"commune": " "},
        {"capacite": 0},
        {"capacite": -3},
        {"latitude": None},
        {"latitude": Decimal(91)},
        {"longitude": Decimal("-180.5")},
        {"statut": "en_service"},
    ],
    ids=[
        "code_vide",
        "nom_espaces",
        "commune_vide",
        "capacite_nulle",
        "capacite_negative",
        "coordonnee_seule",
        "latitude_hors_limites",
        "longitude_hors_limites",
        "statut_non_enum",
    ],
)
def test_invariants_refuses(champs: dict[str, Any]) -> None:
    with pytest.raises((ValueError, TypeError)):
        _station(**champs)


def test_replace_revalide() -> None:
    """dataclasses.replace repasse par __post_init__ : pas de contournement."""
    with pytest.raises(ValueError):
        replace(_station(), capacite=0)


def test_statut_hors_service() -> None:
    assert not _station(statut=StatutStation.FERMEE).en_service
