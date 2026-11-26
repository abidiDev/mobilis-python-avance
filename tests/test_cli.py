"""Tests T-14 : commande `mobilis`, chemins configurables et codes de sortie.

Un mini-kit synthétique est écrit dans un dossier temporaire ; aucune donnée
du kit officiel ni serveur HTTP n'est nécessaire.
"""

import csv
import gzip
import json
from pathlib import Path

import pytest

from mobilis import cli
from mobilis.services.etat_reseau import EtatBorne

STATIONS = [
    "Code station;Nom;Commune;Capacité;Latitude;Longitude;Statut;Mise en service",
    "MB-0001;Hôpital;Valmont;10;45,78;4,87;en_service;16/12/2017",
    "MB-0002;Gare;Valmont;NC;45,76;4,84;En service ;06/02/2023",
    "MB-0003;Mairie;Valmont;8;45,75;4,83;FERMEE;06/02/2020",
]
TRAJETS = [
    # Abonné annuel, 25 min en septembre : 0,00 €
    [
        "T1",
        "A1",
        "V1",
        "mecanique",
        "MB-0001",
        "2026-09-10T08:00:00+02:00",
        "MB-0002",
        "2026-09-10T08:25:00+02:00",
        "1000",
    ],
    # Occasionnel électrique 20 min le 05/10 : 3,70 € (E4)
    [
        "T2",
        "",
        "V2",
        "electrique",
        "MB-0002",
        "2026-10-05T18:00:00+02:00",
        "MB-0001",
        "05/10/2026 18:20:00",
        "900",
    ],
    [
        "T2",
        "",
        "V2",
        "electrique",
        "MB-0002",
        "2026-10-05T18:00:00+02:00",
        "MB-0001",
        "05/10/2026 18:20:00",
        "900",
    ],
]
FORMULE = {
    "minutes_incluses": 30,
    "tranche_minutes": 30,
    "prix_tranche": "1.00",
    "supplement_electrique_tranche": "0.50",
    "frais_deblocage": "0.00",
    "plafond_jour": "12.00",
}
OCCASIONNEL_2025 = FORMULE | {
    "minutes_incluses": 0,
    "tranche_minutes": 15,
    "prix_tranche": "0.60",
    "supplement_electrique_tranche": "0.40",
    "frais_deblocage": "1.00",
    "plafond_jour": None,
}
OCCASIONNEL_2026 = OCCASIONNEL_2025 | {
    "prix_tranche": "0.75",
    "supplement_electrique_tranche": "0.50",
    "frais_deblocage": "1.20",
}


def _grille(du: str, occasionnel: dict[str, object]) -> dict[str, object]:
    formules = {nom: FORMULE for nom in ("annuel", "mensuel", "solidaire")}
    return {"en_vigueur_du": du, "formules": formules | {"occasionnel": occasionnel}}


@pytest.fixture
def kit(tmp_path: Path) -> Path:
    (tmp_path / "stations.csv").write_bytes(("\r\n".join(STATIONS) + "\r\n").encode("cp1252"))
    with gzip.open(tmp_path / cli.FICHIERS["trajets"], "wt", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            [
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
        )
        ecrivain.writerows(TRAJETS)
    abonne = {"id": "A1", "formule": "annuel", "debut": "2024-01-01", "fin": None, "commune": "V"}
    (tmp_path / "abonnes.jsonl").write_text(json.dumps(abonne) + "\n{abîmé\n", encoding="utf-8")
    tarifs = {
        "devise": "EUR",
        "penalite_non_restitution": "150.00",
        "seuil_non_restitution_heures": 24,
        "grilles": [
            _grille("2025-01-01", OCCASIONNEL_2025),
            _grille("2026-10-01", OCCASIONNEL_2026),
        ],
    }
    (tmp_path / "tarifs.json").write_text(json.dumps(tarifs), encoding="utf-8")
    return tmp_path


def _json(capsys: pytest.CaptureFixture[str], argv: list[str]) -> dict[str, object]:
    assert cli.main(argv) == cli.SUCCES
    resultat: dict[str, object] = json.loads(capsys.readouterr().out)
    return resultat


def test_stations(kit: Path, capsys: pytest.CaptureFixture[str]) -> None:
    resultat = _json(capsys, ["stations", "--donnees", str(kit), "--json"])
    assert (resultat["stations"], resultat["exploitables"]) == (3, 1)
    assert resultat["non_exploitables"] == {
        "MB-0002": "capacité inconnue",
        "MB-0003": "statut fermee",
    }


def test_variable_d_environnement(
    kit: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOBILIS_DONNEES", str(kit))
    assert cli.main(["stations"]) == cli.SUCCES
    assert "Stations exploitables : 1" in capsys.readouterr().out


def test_frequentation(kit: Path, capsys: pytest.CaptureFixture[str]) -> None:
    resultat = _json(capsys, ["frequentation", "--donnees", str(kit), "--json"])
    assert resultat["trajets"] == 2
    anomalies = resultat["anomalies"]
    assert isinstance(anomalies, dict)
    assert anomalies[f"{cli.FICHIERS['trajets']}:DOUBLON_IDENTIQUE"] == 1


def test_facturation_et_effet_prix(kit: Path, capsys: pytest.CaptureFixture[str]) -> None:
    resultat = _json(capsys, ["facturation", "--donnees", str(kit), "--json"])
    assert resultat["total"] == "3.70"
    # Ancienne grille sur T2 : 1,00 + 2 × 0,60 + 2 × 0,40 = 3,00 € -> effet +0,70 €
    assert resultat["effet_prix_par_mois"] == {"2026-09": "0.00", "2026-10": "0.70"}


def test_journal_exporte_en_csv(kit: Path, tmp_path: Path) -> None:
    journal = tmp_path / "journal.csv"
    assert cli.main(["facturation", "--donnees", str(kit), "--journal", str(journal)]) == 0
    with journal.open(encoding="utf-8", newline="") as flux:
        codes = {ligne["code_anomalie"] for ligne in csv.DictReader(flux, delimiter=";")}
    assert {"JSON_INVALIDE", "DOUBLON_IDENTIQUE", "CAPACITE_INCONNUE"} <= codes


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["stations"], "dossier des données inconnu"),
        (["stations", "--donnees", "dossier-absent"], "fichier introuvable"),
    ],
)
def test_donnees_absentes_code_1(
    argv: list[str],
    message: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MOBILIS_DONNEES", raising=False)
    assert cli.main(argv) == cli.ERREUR_DONNEES
    assert message in capsys.readouterr().err


def test_tarifs_invalides_code_1(kit: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (kit / "tarifs.json").write_text('{"devise": "EUR"}', encoding="utf-8")
    assert cli.main(["facturation", "--donnees", str(kit)]) == cli.ERREUR_DONNEES
    assert "tarifs invalides" in capsys.readouterr().err


def test_usage_incorrect_code_2() -> None:
    with pytest.raises(SystemExit) as sortie:
        cli.main(["inconnue"])
    assert sortie.value.code == 2


def test_etat_avec_api_simulee(
    kit: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock de l'API : aucune requête réseau, rapprochement avec le référentiel."""
    etats = {
        "MB-0001": EtatBorne("MB-0001", velos_disponibles=0, places_libres=10),
        "MB-0003": EtatBorne("MB-0003", velos_disponibles=8, places_libres=0),
        "MB-0099": EtatBorne("MB-0099", velos_disponibles=1, places_libres=1),
    }

    def lire_etat(code: str) -> EtatBorne:
        if code == "MB-0002":
            raise OSError("504")
        return etats[code]

    monkeypatch.setattr(
        cli,
        "ouvrir_bornes",
        lambda _args: (["MB-0001", "MB-0002", "MB-0003", "MB-0099"], lire_etat),
    )
    resultat = _json(capsys, ["etat", "--donnees", str(kit), "--json"])
    assert resultat["vides"] == ["MB-0001"]
    assert resultat["pleines"] == ["MB-0003"]
    assert resultat["inconnues_du_referentiel"] == ["MB-0099"]
    assert resultat["exploitables_sans_reponse"] == []
    assert resultat["erreurs"] == {"MB-0002": "OSError: 504"}


def test_etat_api_injoignable_code_3(
    kit: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def refus(_args: object) -> cli.Bornes:
        raise ConnectionRefusedError("connexion refusée")

    monkeypatch.setattr(cli, "ouvrir_bornes", refus)
    assert cli.main(["etat", "--donnees", str(kit)]) == cli.ERREUR_API
    assert "injoignable" in capsys.readouterr().err
