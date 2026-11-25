"""Tests unitaires de chaque étape du pipeline de générateurs des trajets."""

import csv
import gzip
from collections.abc import Iterator
from pathlib import Path

from mobilis.adapters.trajets_csv import (
    IndexDedoublonnage,
    LigneBrute,
    dedoublonner,
    lire_lignes_brutes,
    normaliser_lignes,
)
from mobilis.domain.anomalies import CollecteurAnomalies

_ENTETE = [
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


def _valeurs(identifiant: str, debut: str = "2026-08-03T08:00:00+02:00") -> dict[str, str]:
    ligne = [identifiant, "", "V001", "mecanique", "MB-0001", debut, "", "", ""]
    return dict(zip(_ENTETE, ligne, strict=True))


def test_lire_lignes_brutes_numerote_et_ecarte_colonnes_invalides(tmp_path: Path) -> None:
    fichier = tmp_path / "t.csv.gz"
    with gzip.open(fichier, "wt", encoding="utf-8", newline="") as cible:
        ecrivain = csv.writer(cible)
        ecrivain.writerow(_ENTETE)
        ecrivain.writerow(list(_valeurs("T1").values()))
        ecrivain.writerow(["T2", "trop", "court"])
        ecrivain.writerow(list(_valeurs("T3").values()))
    journal = CollecteurAnomalies()

    lignes = list(lire_lignes_brutes(fichier, journal.signaler))

    assert [(lg.numero, lg.valeurs["trajet_id"]) for lg in lignes] == [(2, "T1"), (4, "T3")]
    assert [a.code_anomalie for a in journal.elements] == ["COLONNES_INVALIDES"]
    assert journal.elements[0].ligne == 3


def test_normaliser_est_paresseux() -> None:
    """L'étape ne lit une ligne amont que lorsqu'on lui demande un trajet."""
    consommees: list[int] = []

    def source() -> Iterator[LigneBrute]:
        for numero in range(2, 1_000_000):
            consommees.append(numero)
            yield LigneBrute(numero, _valeurs(f"T{numero}"))

    flux = normaliser_lignes(source(), lambda _: None, "t.csv.gz")
    premier = next(flux)

    assert premier.trajet.trajet_id == "T2"
    assert consommees == [2]


def test_normaliser_saute_ligne_invalide_sans_arreter_le_flux() -> None:
    journal = CollecteurAnomalies()
    lignes = [
        LigneBrute(2, _valeurs("T1", debut="pas une date")),
        LigneBrute(3, _valeurs("T2")),
    ]

    lus = list(normaliser_lignes(lignes, journal.signaler, "t.csv.gz"))

    assert [lu.trajet.trajet_id for lu in lus] == ["T2"]
    assert journal.elements[0].ligne == 2


def test_dedoublonner_garde_la_premiere_occurrence(tmp_path: Path) -> None:
    journal = CollecteurAnomalies()
    lignes = [LigneBrute(n, _valeurs(i)) for n, i in [(2, "T1"), (3, "T2"), (4, "T1")]]
    lus = normaliser_lignes(lignes, journal.signaler, "t.csv.gz")
    index = IndexDedoublonnage(tmp_path)
    try:
        trajets = list(dedoublonner(lus, index, journal.signaler, "t.csv.gz"))
    finally:
        index.fermer()

    assert [t.trajet_id for t in trajets] == ["T1", "T2"]
    assert [(a.code_anomalie, a.ligne) for a in journal.elements] == [("DOUBLON_IDENTIQUE", 4)]
