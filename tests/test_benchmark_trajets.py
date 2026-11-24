"""Tests du générateur synthétique et de la recette de scalabilité US-02."""

import csv
import gzip
from collections import Counter
from pathlib import Path

import pytest

from mobilis.adapters.trajets_csv import LecteurTrajetsGzip
from mobilis.domain.anomalies import Anomalie
from scripts.benchmark_trajets import creer_fichier_synthetique, lancer_benchmark

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
_LIGNE = [
    "T01",
    "",
    "V01",
    "mecanique",
    "MB-0001",
    "2026-08-03T08:00:00+02:00",
    "MB-0002",
    "2026-08-03T08:20:00+02:00",
    "1200",
]


def _source(path: Path) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as flux:
        writer = csv.writer(flux)
        writer.writerow(_COLONNES)
        writer.writerow(_LIGNE)
        writer.writerow(_LIGNE)


def test_multiplication_conserve_doublons_internes_et_isole_copies(
    tmp_path: Path,
) -> None:
    source = tmp_path / "officiel.csv.gz"
    cible = tmp_path / "synthetique.csv.gz"
    _source(source)
    avant = source.read_bytes()
    assert creer_fichier_synthetique(source, cible, facteur=2) == 4
    assert source.read_bytes() == avant

    compteurs: Counter[str] = Counter()

    def signaler(a: Anomalie) -> None:
        compteurs[a.code_anomalie] += 1

    lecteur = LecteurTrajetsGzip(cible)
    resultats = list(lecteur.lire(signaler))
    assert [t.trajet_id for t in resultats] == ["T01-S000", "T01-S001"]
    assert compteurs["DOUBLON_IDENTIQUE"] == 2
    assert lecteur.taille_index_octets is not None
    assert lecteur.taille_index_octets > 0


def test_benchmark_x100_sur_petit_echantillon_et_cleanup(tmp_path: Path) -> None:
    source = tmp_path / "officiel.csv.gz"
    _source(source)
    rapport = lancer_benchmark(
        source,
        facteur=100,
        max_lignes=2,
        repertoire_temp=tmp_path,
    )
    assert rapport["lignes_synthetiques"] == 200
    assert rapport["trajets_uniques_valides"] == 100
    assert rapport["doublons_identiques"] == 100
    assert rapport["pic_tracemalloc_octets"] is None
    assert isinstance(rapport["index_sqlite_octets"], int)
    assert rapport["temps_analyse_secondes"] >= 0
    assert not list(tmp_path.glob("mobilis-bench-*"))


def test_mesure_tracemalloc_disponible_sur_petit_echantillon(tmp_path: Path) -> None:
    source = tmp_path / "officiel.csv.gz"
    _source(source)
    rapport = lancer_benchmark(
        source, facteur=2, tracer_memoire=True, repertoire_temp=tmp_path
    )
    assert rapport["trajets_uniques_valides"] == 2
    assert isinstance(rapport["pic_tracemalloc_octets"], int)
    assert rapport["pic_tracemalloc_octets"] > 0


@pytest.mark.parametrize("facteur", [0, 101, -1])
def test_rejette_facteur_abusif(tmp_path: Path, facteur: int) -> None:
    source = tmp_path / "officiel.csv.gz"
    _source(source)
    with pytest.raises(ValueError, match="facteur"):
        lancer_benchmark(source, facteur=facteur)


def test_rejette_ecrasement_de_la_source(tmp_path: Path) -> None:
    source = tmp_path / "officiel.csv.gz"
    _source(source)
    with pytest.raises(ValueError, match="écraser"):
        creer_fichier_synthetique(source, source, facteur=2)
