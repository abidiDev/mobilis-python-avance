"""Tests T-05/T-06 : lecture de stations.csv et référentiel exploitable."""

from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from mobilis.adapters.stations_csv import (
    COLONNES,
    ENCODAGE,
    LecteurStationsCsv,
    LigneRejetee,
    normaliser_statut,
)
from mobilis.domain.anomalies import CollecteurAnomalies
from mobilis.domain.contracts import SourceStations
from mobilis.domain.models import StatutStation
from mobilis.services.stations import construire_referentiel

LIGNES = [
    # 2 : ligne propre
    "MB-0001;Hôpital Lamartine;Valmont;37;45,78525;4,87212;en_service;16/12/2017",
    # 3 : statut avec espace final, nom avec espaces, capacité avec espace
    "MB-0002;Rue des Forges  ;Bréval; 31;45,76047;4,84165;En service ;06/02/2023",
    # 4 : capacité NC, date ISO
    "MB-0003;Square Sainte-Hélène;Valmont;NC;45,75;4,83;EN SERVICE;2015-03-17",
    # 5 : coordonnées inversées
    "MB-0004;Quai Victor-Hugo;Montfleury;20;4,79377;45,73036;HS;01/01/2020",
    # 6 : coordonnées absentes, station fermée
    "MB-0005;Avenue Saint-Éloi;Valmont;24;;;FERMEE;01/01/2019",
    # 7 et 8 : code répété, la version la plus récente doit gagner
    "MB-0006;Marché de la Poste;Valmont;36;45,75899;4,83158;Hors service;15/05/2017",
    "MB-0006;Marché de la Poste;Valmont;40;45,75899;4,83158;En service;26/04/2026",
    # 9 : statut inconnu -> rejet ; 10 : code invalide -> rejet ; 11 : date illisible
    "MB-0007;Gare;Valmont;20;45,7;4,8;en travaux;01/01/2020",
    "MB-07;Gare;Valmont;20;45,7;4,8;en_service;01/01/2020",
    "MB-0008;Gare;Valmont;20;45,7;4,8;en_service;31/02/2020",
]


@pytest.fixture
def fichier(tmp_path: Path) -> Path:
    chemin = tmp_path / "stations.csv"
    contenu = "\r\n".join([";".join(COLONNES), *LIGNES]) + "\r\n"
    chemin.write_bytes(contenu.encode(ENCODAGE))
    return chemin


def test_encodage_cp1252_et_accents(fichier: Path) -> None:
    lecteur: SourceStations = LecteurStationsCsv(fichier)
    stations = list(lecteur.lire(lambda _: None))
    assert stations[0].nom == "Hôpital Lamartine"
    assert stations[1].commune == "Bréval"


def test_lecture_ne_s_arrete_pas_et_compte_chaque_anomalie(fichier: Path) -> None:
    journal = CollecteurAnomalies()
    stations = list(LecteurStationsCsv(fichier).lire(journal.signaler))

    assert [s.code for s in stations] == [f"MB-000{i}" for i in (1, 2, 3, 4, 5, 6, 6)]
    codes = Counter(a.code_anomalie for a in journal.elements)
    assert codes == {
        "STATUT_NON_NORMALISE": 6,
        "ESPACES_SUPERFLUS": 2,
        "CAPACITE_INCONNUE": 1,
        "DATE_FORMAT_ISO": 1,
        "COORDONNEES_INVERSEES": 1,
        "COORDONNEES_ABSENTES": 1,
        "LIGNE_REJETEE": 3,
    }
    rejets = [a.ligne for a in journal.elements if a.code_anomalie == "LIGNE_REJETEE"]
    assert rejets == [9, 10, 11]


def test_valeurs_corrigees(fichier: Path) -> None:
    stations = list(LecteurStationsCsv(fichier).lire(lambda _: None))
    par_ligne = {i: s for i, s in enumerate(stations, start=2)}
    assert par_ligne[3].nom == "Rue des Forges" and par_ligne[3].capacite == 31
    assert par_ligne[4].capacite is None and par_ligne[4].mise_en_service == date(2015, 3, 17)
    assert (par_ligne[5].latitude, par_ligne[5].longitude) == (
        Decimal("45.73036"),
        Decimal("4.79377"),
    )
    assert par_ligne[6].latitude is None


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("en_service", StatutStation.EN_SERVICE),
        ("En service ", StatutStation.EN_SERVICE),
        ("EN SERVICE", StatutStation.EN_SERVICE),
        ("Hors service", StatutStation.HORS_SERVICE),
        ("HS", StatutStation.HORS_SERVICE),
        ("FERMEE", StatutStation.FERMEE),
    ],
)
def test_normalisation_des_statuts(brut: str, attendu: StatutStation) -> None:
    assert normaliser_statut(brut) is attendu


def test_statut_inconnu_rejete() -> None:
    with pytest.raises(LigneRejetee):
        normaliser_statut("en travaux")


def test_entetes_inattendus_refuses(tmp_path: Path) -> None:
    chemin = tmp_path / "stations.csv"
    chemin.write_bytes("Code,Nom\nMB-0001,X\n".encode(ENCODAGE))
    with pytest.raises(ValueError, match="En-têtes"):
        list(LecteurStationsCsv(chemin).lire(lambda _: None))


def test_referentiel_de_bout_en_bout(fichier: Path) -> None:
    """Intégration : CSV brut -> lecteur -> service -> référentiel exploitable."""
    journal = CollecteurAnomalies()
    rapport = construire_referentiel(
        LecteurStationsCsv(fichier).lire(journal.signaler), journal.signaler
    )

    assert rapport.versions_lues == 7
    assert [s.code for s in rapport.referentiel] == [f"MB-000{i}" for i in range(1, 7)]
    station_6 = next(s for s in rapport.referentiel if s.code == "MB-0006")
    assert (station_6.capacite, station_6.statut) == (40, StatutStation.EN_SERVICE)
    assert rapport.versions_remplacees[0].mise_en_service == date(2017, 5, 15)
    assert [s.code for s in rapport.exploitables] == ["MB-0001", "MB-0002", "MB-0006"]
    assert rapport.non_exploitables == {
        "MB-0003": "capacité inconnue",
        "MB-0004": "statut hors_service",
        "MB-0005": "statut fermee",
    }
    assert rapport.par_statut()[StatutStation.EN_SERVICE] == 4
    assert [a.code_anomalie for a in journal.elements].count("CODE_REPETE") == 1


def test_version_ancienne_lue_apres_la_recente(fichier: Path) -> None:
    stations = list(LecteurStationsCsv(fichier).lire(lambda _: None))
    inverse = [*stations[:-2], stations[-1], stations[-2]]
    rapport = construire_referentiel(inverse, lambda _: None)
    assert next(s for s in rapport.referentiel if s.code == "MB-0006").capacite == 40


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [("NaN", "4,83"), ("45,75", "Infinity"), ("-Infinity", "4,83")],
)
def test_coordonnees_non_finies_traitees_comme_inconnues(
    tmp_path: Path, latitude: str, longitude: str
) -> None:
    chemin = tmp_path / "stations.csv"
    ligne = f"MB-0001;Test;Valmont;12;{latitude};{longitude};en_service;16/12/2017"
    chemin.write_bytes((";".join(COLONNES) + "\n" + ligne + "\n").encode(ENCODAGE))
    journal = CollecteurAnomalies()
    station = next(LecteurStationsCsv(chemin).lire(journal.signaler))
    assert station.latitude is None and station.longitude is None
    assert [x.code_anomalie for x in journal.elements] == ["COORDONNEES_INVALIDES"]
