"""Tests T-11 : recettes mensuelles par formule et effet du changement de grille."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from test_facturation import ABONNES, CONFIG

from mobilis.domain.models import ConfigurationTarifaire, FormuleAbonnement, Trajet, TypeVelo
from mobilis.services.facturation import MoteurFacturation, RegistreAbonnements, StatutFacturation
from mobilis.services.recettes import analyser_recettes, avec_grille_unique, effet_prix, mois

F = FormuleAbonnement
D = Decimal


def _trajet(tid: str, abonne: str | None, debut: str, minutes: int | None) -> Trajet:
    instant = datetime.fromisoformat(debut)
    fin = None if minutes is None else instant + timedelta(minutes=minutes)
    arrivee = None if minutes is None else "MB-0002"
    return Trajet(tid, abonne, "V1", TypeVelo.MECANIQUE, "MB-0001", instant, arrivee, fin, None)


def _moteur(configuration: ConfigurationTarifaire = CONFIG) -> MoteurFacturation:
    return MoteurFacturation(configuration, RegistreAbonnements(ABONNES), lambda _: None)


TRAJETS = [
    # Août, annuel : 3 × 3 h le même jour -> 15,00 € plafonnés à 12,00 € (E5)
    _trajet("T1", "A-ANNUEL", "2026-08-12T06:00:00+02:00", 180),
    _trajet("T2", "A-ANNUEL", "2026-08-12T10:00:00+02:00", 180),
    _trajet("T3", "A-ANNUEL", "2026-08-12T14:00:00+02:00", 180),
    # 31/08 23:30 à Paris = 21:30 UTC : compté en août ; occasionnel 20 min = 2,20 €
    _trajet("T4", None, "2026-08-31T21:30:00+00:00", 20),
    # Octobre : occasionnel 20 min, nouvelle grille = 1,20 + 2 × 0,75 = 2,70 €
    _trajet("T5", None, "2026-10-05T08:00:00+02:00", 20),
    # Octobre : non-restitution = 150,00 €
    _trajet("T6", None, "2026-10-06T08:00:00+02:00", None),
]


def test_mois_local() -> None:
    assert mois(date(2026, 8, 1)) == "2026-08"


def test_recettes_par_mois_et_formule() -> None:
    rapport = analyser_recettes(_moteur(), iter(TRAJETS))

    assert rapport.recettes == {
        ("2026-08", F.ANNUEL): D("12.00"),
        ("2026-08", F.OCCASIONNEL): D("2.20"),
        ("2026-10", F.OCCASIONNEL): D("152.70"),
    }
    assert rapport.economies_plafond[("2026-08", F.ANNUEL)] == D("3.00")
    assert rapport.trajets[("2026-08", F.ANNUEL)] == 3
    assert rapport.statuts[StatutFacturation.PENALITE] == 1
    assert rapport.total() == D("166.90")
    assert rapport.total_mois("2026-10") == D("152.70")


def test_effet_prix_isole_le_changement_de_grille() -> None:
    reel = analyser_recettes(_moteur(), iter(TRAJETS))
    ancienne = analyser_recettes(
        _moteur(avec_grille_unique(CONFIG, date(2025, 1, 1))), iter(TRAJETS)
    )

    ecarts = effet_prix(reel, ancienne)

    # Août utilise déjà l'ancienne grille : aucun effet.
    assert ecarts[("2026-08", F.ANNUEL)] == D("0.00")
    # Octobre : 2,70 € au lieu de 2,20 € pour T5 ; pénalité inchangée.
    assert ecarts[("2026-10", F.OCCASIONNEL)] == D("0.50")


def test_grille_unique_inconnue_refusee() -> None:
    with pytest.raises(ValueError, match="aucune grille"):
        avec_grille_unique(CONFIG, date(2020, 1, 1))
