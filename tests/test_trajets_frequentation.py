"""Tests T-07/T-08 sur jeux synthétiques compressés et en flux."""

import csv
import gzip
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mobilis.adapters.trajets_csv import LecteurTrajetsGzip, convertir_date
from mobilis.domain.anomalies import CollecteurAnomalies
from mobilis.domain.models import Trajet, TypeVelo
from mobilis.services.frequentation import (
    analyser_avec_pic_memoire,
    analyser_frequentation,
)

_COLONNES = [
    "trajet_id",
    "abonne_id",
    "velo_id",
    "type_velo",
    "station_depart",
    "debut",
    "station_arrivee",
    "fin",
    "distance_m",
]


def _trajet_ligne(
    identifiant: str,
    debut: str = "2026-08-03T08:00:00+02:00",
    fin: str = "2026-08-03T08:30:00+02:00",
) -> list[str]:
    return [identifiant, "", "V001", "mecanique", "MB-0001", debut, "MB-0002", fin, "1200"]


def _gzip_csv(path: Path, lignes: list[list[str]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as cible:
        writer = csv.writer(cible)
        writer.writerow(_COLONNES)
        writer.writerows(lignes)


@pytest.mark.parametrize(
    ("valeur", "attendu"),
    [
        ("2026-08-03T08:00:00+02:00", datetime(2026, 8, 3, 6, tzinfo=UTC)),
        ("2026-08-03T06:00:00Z", datetime(2026, 8, 3, 6, tzinfo=UTC)),
        ("03/08/2026 08:00:00", datetime(2026, 8, 3, 6, tzinfo=UTC)),
    ],
)
def test_trois_formats_de_dates(valeur: str, attendu: datetime) -> None:
    journal = CollecteurAnomalies()
    resultat = convertir_date(valeur, journal.signaler, "trajets.csv.gz", 2, "T1", "debut")
    assert resultat == attendu


def test_heure_ambigue_signalee() -> None:
    journal = CollecteurAnomalies()
    moment = convertir_date(
        "25/10/2026 02:30:00", journal.signaler, "trajets.csv.gz", 2, "T1", "debut"
    )
    assert moment == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert journal.elements[0].code_anomalie == "HEURE_LOCALE_AMBIGUE"


def test_heure_inexistante_rejetee() -> None:
    with pytest.raises(ValueError, match="inexistante"):
        convertir_date("29/03/2026 02:30:00", lambda _: None, "trajets.csv.gz", 2, "T1", "debut")


def test_lecture_en_flux_dedoublonne_et_signale(tmp_path: Path) -> None:
    fichier = tmp_path / "trajets.csv.gz"
    _gzip_csv(
        fichier,
        [
            _trajet_ligne("T1"),
            _trajet_ligne("T1"),
            _trajet_ligne("T2", "03/08/2026 09:00:00", "2026-08-03T09:20:00+02:00"),
            _trajet_ligne("T3", "incorrect", "2026-08-03T11:00:00+02:00"),
        ],
    )
    journal = CollecteurAnomalies()
    trajets = list(LecteurTrajetsGzip(fichier).lire(journal.signaler))
    assert [t.trajet_id for t in trajets] == ["T1", "T2"]
    assert {a.code_anomalie for a in journal.elements} == {
        "DOUBLON_IDENTIQUE",
        "DONNEE_INVALIDE",
    }


def test_identifiant_en_conflit_ne_remplace_pas_la_premiere_ligne(tmp_path: Path) -> None:
    fichier = tmp_path / "trajets.csv.gz"
    _gzip_csv(
        fichier,
        [
            _trajet_ligne("T1"),
            _trajet_ligne("T1", "2026-08-03T08:05:00+02:00"),
        ],
    )
    journal = CollecteurAnomalies()
    trajets = list(LecteurTrajetsGzip(fichier).lire(journal.signaler))
    assert len(trajets) == 1
    assert journal.elements[0].code_anomalie == "ID_EN_CONFLIT"


def test_distance_invalide_ne_supprime_pas_le_trajet(tmp_path: Path) -> None:
    fichier = tmp_path / "trajets.csv.gz"
    ligne = _trajet_ligne("T1")
    ligne[-1] = "NC"
    _gzip_csv(fichier, [ligne])
    journal = CollecteurAnomalies()
    trajets = list(LecteurTrajetsGzip(fichier).lire(journal.signaler))
    assert trajets[0].distance_m is None
    assert journal.elements[0].code_anomalie == "DISTANCE_INVALIDE"


def test_frequentation_matin_et_soir() -> None:
    trajets = (
        Trajet(
            f"T{i}",
            None,
            "V1",
            TypeVelo.MECANIQUE,
            "MB-0001",
            datetime(2026, 8, 3, 6, tzinfo=UTC),
            "MB-0002",
            datetime(2026, 8, 3, 16, tzinfo=UTC),
            None,
        )
        for i in range(3)
    )
    rapport = analyser_frequentation(trajets)
    assert rapport.trajets == 3
    assert rapport.flux_stations["MB-0001"].departs_matin == 3
    assert rapport.flux_stations["MB-0002"].arrivees_soir == 3
    assert rapport.flux_stations["MB-0001"].solde_matin == -3
    assert rapport.profils_departs[(False, 8)] == 3


def test_frequentation_weekend_et_retour_absent() -> None:
    trajet = Trajet(
        "T1",
        None,
        "V1",
        TypeVelo.ELECTRIQUE,
        "MB-0001",
        datetime(2026, 8, 2, 7, tzinfo=UTC),
        None,
        None,
        None,
    )
    rapport, pic = analyser_avec_pic_memoire(iter([trajet]))
    assert rapport.sans_retour == 1
    assert rapport.profils_departs[(True, 9)] == 1
    assert sum(rapport.profils_arrivees.values()) == 0
    assert pic >= 0
