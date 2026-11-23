"""Tests des modèles, du collecteur et des ports partagés T-03."""

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from mobilis.domain.anomalies import Anomalie, CollecteurAnomalies, NiveauAnomalie
from mobilis.domain.contracts import SourceTrajets
from mobilis.domain.models import (
    ConfigurationTarifaire,
    FormuleAbonnement,
    GrilleTarifaire,
    PeriodeAbonnement,
    Station,
    StatutStation,
    TarifFormule,
    Trajet,
    TypeVelo,
)


def test_station_immutable_preserves_code_and_nullable_capacity() -> None:
    station = Station(
        code="MB-0033",
        nom="Pont de la Mairie",
        commune="Valmont",
        capacite=None,
        latitude=Decimal("45.75899"),
        longitude=Decimal("4.83974"),
        statut=StatutStation.EN_SERVICE,
        mise_en_service=date(2020, 9, 14),
    )
    assert station.code == "MB-0033"
    assert station.capacite is None
    with pytest.raises(FrozenInstanceError):
        station.code = "MB-33"  # type: ignore[misc]


def test_station_same_code_can_have_distinct_versions() -> None:
    a = Station(
        "MB-0033",
        "Pont de la Mairie",
        "Valmont",
        36,
        None,
        None,
        StatutStation.EN_SERVICE,
        date(2020, 9, 14),
    )
    b = Station(
        "MB-0033",
        "Pont de la Mairie",
        "Valmont",
        44,
        None,
        None,
        StatutStation.EN_SERVICE,
        date(2021, 1, 25),
    )
    assert a.code == b.code
    assert a != b


def test_trajet_may_have_missing_return_without_implying_a_charge() -> None:
    trajet = Trajet(
        trajet_id="T0000003",
        abonne_id=None,
        velo_id="V00829",
        type_velo=TypeVelo.ELECTRIQUE,
        station_depart="MB-0080",
        debut=datetime(2026, 8, 1, 0, 13, tzinfo=UTC),
        station_arrivee=None,
        fin=None,
        distance_m=None,
    )
    assert trajet.fin is None
    assert trajet.abonne_id is None


def test_subscription_periods_keep_same_subscriber_id() -> None:
    first = PeriodeAbonnement(
        "A003495",
        FormuleAbonnement.ANNUEL,
        date(2024, 3, 27),
        date(2025, 3, 27),
        "Valmont",
    )
    second = PeriodeAbonnement(
        "A003495",
        FormuleAbonnement.MENSUEL,
        date(2025, 3, 28),
        None,
        "Valmont",
    )
    assert first.id == second.id
    assert first != second


def test_tariff_values_remain_decimal() -> None:
    formule = TarifFormule(
        minutes_incluses=30,
        tranche_minutes=30,
        prix_tranche=Decimal("1.20"),
        supplement_electrique_tranche=Decimal("0.60"),
        frais_deblocage=Decimal("0.00"),
        plafond_jour=Decimal("14.00"),
    )
    config = ConfigurationTarifaire(
        devise="EUR",
        penalite_non_restitution=Decimal("150.00"),
        seuil_non_restitution_heures=24,
        grilles=(
            GrilleTarifaire(
                date(2026, 10, 1),
                {FormuleAbonnement.ANNUEL: formule},
            ),
        ),
    )
    assert config.grilles[0].formules[FormuleAbonnement.ANNUEL].prix_tranche == Decimal("1.20")


def test_collector_emits_uniform_anomalies_without_global_state() -> None:
    journal = CollecteurAnomalies()
    autre = CollecteurAnomalies()
    anomalie = Anomalie(
        fichier_source="stations.csv",
        ligne=29,
        identifiant="MB-0028",
        champ="Capacité",
        code_anomalie="CAPACITE_INCONNUE",
        niveau=NiveauAnomalie.ALERTE,
        valeur_observee="NC",
        traitement_propose="Conserver None et demander validation",
    )
    journal.signaler(anomalie)
    assert journal.elements == (anomalie,)
    assert autre.elements == ()


def test_reader_protocol_is_structurally_satisfied() -> None:
    class FauxLecteur:
        def lire(self, signaler: object) -> Iterator[Trajet]:
            yield Trajet(
                "T0000001",
                None,
                "V00616",
                TypeVelo.MECANIQUE,
                "MB-0015",
                datetime(2026, 8, 1, tzinfo=UTC),
                None,
                None,
                None,
            )

    lecteur: SourceTrajets = FauxLecteur()
    assert next(lecteur.lire(lambda _: None)).trajet_id == "T0000001"
