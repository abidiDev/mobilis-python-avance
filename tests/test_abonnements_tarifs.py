"""Tests T-09 : lecteurs abonnés/tarifs et contrat de tarification."""

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from mobilis.adapters.abonnes_jsonl import LecteurAbonnementsJsonl
from mobilis.adapters.tarifs_json import LecteurTarifsJson, TarifsInvalides
from mobilis.domain.anomalies import CollecteurAnomalies
from mobilis.domain.contracts import SourceAbonnements, SourceTarifs
from mobilis.domain.models import FormuleAbonnement, TarifFormule, TypeVelo
from mobilis.services.tarification import (
    Tarification,
    TarificationAbonnement,
    TarificationOccasionnelle,
    arrondir,
    strategie_pour,
    tranches_entamees,
)

ANNUEL = TarifFormule(30, 30, Decimal("1.00"), Decimal("0.50"), Decimal("0.00"), Decimal("12.00"))
OCCASIONNEL = TarifFormule(0, 15, Decimal("0.60"), Decimal("0.40"), Decimal("1.00"), None)


# --- Abonnements -------------------------------------------------------------


def test_abonnes_lignes_abimees_signalees_et_historique_conserve(tmp_path: Path) -> None:
    fichier = tmp_path / "abonnes.jsonl"
    a1 = {"id": "A1", "formule": "annuel", "debut": "2024-03-27", "fin": "2025-03-27"}
    a1_bis = {"id": "A1", "formule": " Mensuel", "debut": "2025-03-28", "fin": None}
    a3 = {"id": "A3", "formule": "premium", "debut": "2024-01-01", "fin": None}
    lignes = [
        json.dumps(a1 | {"commune": "Valmont"}),
        "",
        json.dumps(a1_bis | {"commune": "Valmont"}),
        '{"id": "A2", "formule": "annuel", "debut": "2023-0',
        json.dumps(a3 | {"commune": "X"}),
    ]
    fichier.write_text("\n".join(lignes), encoding="utf-8")
    journal = CollecteurAnomalies()
    lecteur: SourceAbonnements = LecteurAbonnementsJsonl(fichier)

    periodes = list(lecteur.lire(journal.signaler))

    assert [(p.id, p.formule) for p in periodes] == [
        ("A1", FormuleAbonnement.ANNUEL),
        ("A1", FormuleAbonnement.MENSUEL),
    ]
    assert periodes[1].fin is None
    codes = [(a.code_anomalie, a.ligne) for a in journal.elements]
    assert codes == [
        ("JSON_INVALIDE", 2),
        ("FORMULE_NON_NORMALISEE", 3),
        ("JSON_INVALIDE", 4),
        ("VALEUR_INVALIDE", 5),
    ]


# --- Tarifs ------------------------------------------------------------------


def _tarifs(tmp_path: Path, **surcharge: object) -> Path:
    formule = {
        "minutes_incluses": 30,
        "tranche_minutes": 30,
        "prix_tranche": "1.00",
        "supplement_electrique_tranche": "0.50",
        "frais_deblocage": "0.00",
        "plafond_jour": "12.00",
    }
    formule.update(surcharge)
    donnees = {
        "devise": "EUR",
        "penalite_non_restitution": "150.00",
        "seuil_non_restitution_heures": 24,
        "grilles": [
            {
                "en_vigueur_du": d,
                "formules": {f.value: formule for f in FormuleAbonnement},
            }
            for d in ("2026-10-01", "2025-01-01")
        ],
    }
    fichier = tmp_path / "tarifs.json"
    fichier.write_text(json.dumps(donnees), encoding="utf-8")
    return fichier


def test_tarifs_en_decimal_et_grilles_triees(tmp_path: Path) -> None:
    lecteur: SourceTarifs = LecteurTarifsJson(_tarifs(tmp_path))
    config = lecteur.lire(lambda _: None)

    assert [g.en_vigueur_du for g in config.grilles] == [date(2025, 1, 1), date(2026, 10, 1)]
    tarif = config.grilles[0].formules[FormuleAbonnement.ANNUEL]
    assert tarif.prix_tranche == Decimal("1.00")
    assert isinstance(config.penalite_non_restitution, Decimal)
    with pytest.raises(TypeError):
        config.grilles[0].formules[FormuleAbonnement.ANNUEL] = tarif  # type: ignore[index]


@pytest.mark.parametrize(
    "surcharge",
    [
        {"prix_tranche": 1.2},
        {"prix_tranche": "abc"},
        {"prix_tranche": "-1"},
        {"prix_tranche": "NaN"},
        {"prix_tranche": "Infinity"},
        {"tranche_minutes": 0},
    ],
)
def test_tarifs_invalides_refuses(tmp_path: Path, surcharge: dict[str, object]) -> None:
    with pytest.raises(TarifsInvalides):
        LecteurTarifsJson(_tarifs(tmp_path, **surcharge)).lire(lambda _: None)


# --- Contrat de tarification -------------------------------------------------


@pytest.mark.parametrize(
    ("duree", "tranche", "attendu"),
    [
        (timedelta(0), 30, 0),
        (timedelta(seconds=1), 30, 1),
        (timedelta(minutes=30), 30, 1),
        (timedelta(minutes=30, seconds=1), 30, 2),
        (timedelta(minutes=-5), 30, 0),
    ],
)
def test_tranche_entamee_des_la_premiere_seconde(
    duree: timedelta, tranche: int, attendu: int
) -> None:
    assert tranches_entamees(duree, tranche) == attendu


def test_arrondi_moitie_vers_le_haut() -> None:
    assert arrondir(Decimal("0.125")) == Decimal("0.13")
    assert arrondir(Decimal("0.124")) == Decimal("0.12")


def test_deux_strategies_respectent_le_contrat() -> None:
    abonnement: Tarification = strategie_pour(FormuleAbonnement.ANNUEL, ANNUEL)
    occasionnel: Tarification = strategie_pour(FormuleAbonnement.OCCASIONNEL, OCCASIONNEL)

    assert isinstance(abonnement, TarificationAbonnement)
    assert isinstance(occasionnel, TarificationOccasionnelle)
    # R4 : 61 min d'annuel -> 31 min d'usage -> 2 tranches
    assert abonnement.prix_trajet(timedelta(minutes=61), TypeVelo.MECANIQUE) == Decimal("2.00")
    # Occasionnel : frais 1,00 + 2 tranches de 15 min ; R5 : 2 tranches électriques
    assert occasionnel.prix_trajet(timedelta(minutes=20), TypeVelo.ELECTRIQUE) == Decimal("3.00")
    # R6 : seul l'abonnement est plafonné
    assert abonnement.total_journee(Decimal("15.00")) == Decimal("12.00")
    assert occasionnel.total_journee(Decimal("15.00")) == Decimal("15.00")
    assert abonnement.plafonnee and not occasionnel.plafonnee


def test_tarification_abstraite_non_instanciable() -> None:
    with pytest.raises(TypeError):
        Tarification(ANNUEL)  # type: ignore[abstract]


@pytest.mark.parametrize("contenu", ["{", "null", '{"grilles": []}'])
def test_configuration_malformee_renvoie_erreur_metier(tmp_path: Path, contenu: str) -> None:
    chemin = tmp_path / "tarifs.json"
    chemin.write_text(contenu, encoding="utf-8")
    with pytest.raises(TarifsInvalides):
        LecteurTarifsJson(chemin).lire(lambda _: None)
