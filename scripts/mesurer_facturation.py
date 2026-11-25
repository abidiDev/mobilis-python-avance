"""Mesure reproductible de l'US-03 (facturation) à partir des fichiers bruts du kit.

Nécessite le lecteur de trajets de la PR #26 (US-02). Exécution :
python scripts/mesurer_facturation.py ../mobilis-kit/donnees

Le script affiche en JSON : recettes par mois et formule avec la vraie
configuration, recettes si l'ancienne grille s'appliquait toute la période,
effet prix du 1er octobre 2026, statuts de facturation et anomalies.
"""

import argparse
import csv
import json
import time
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from mobilis.adapters.abonnes_jsonl import LecteurAbonnementsJsonl
from mobilis.adapters.tarifs_json import LecteurTarifsJson
from mobilis.adapters.trajets_csv import LecteurTrajetsGzip
from mobilis.domain.anomalies import Anomalie
from mobilis.services.facturation import MoteurFacturation, RegistreAbonnements
from mobilis.services.recettes import (
    RapportRecettes,
    analyser_recettes,
    avec_grille_unique,
    effet_prix,
)

TRAJETS = "trajets_2026-08_2026-10.csv.gz"


def codes_stations(chemin: Path) -> set[str]:
    """Codes du référentiel pour R12, en attendant le lecteur complet de l'US-01 (#10)."""
    with chemin.open(encoding="cp1252", newline="") as flux:
        return {ligne["Code station"].strip() for ligne in csv.DictReader(flux, delimiter=";")}


def _tableau(rapport: RapportRecettes) -> dict[str, dict[str, str]]:
    sortie: dict[str, dict[str, str]] = {}
    for (m, formule), montant in sorted(rapport.recettes.items()):
        sortie.setdefault(m, {})[formule.value] = str(montant)
    for m, ligne in sortie.items():
        ligne["total"] = str(rapport.total_mois(m))
    return sortie


def main() -> None:
    parser = argparse.ArgumentParser(description="Mobilis — mesure facturation US-03")
    parser.add_argument("donnees", type=Path, help="Dossier donnees/ du kit (non versionné)")
    dossier = parser.parse_args().donnees

    anomalies: Counter[str] = Counter()

    def signaler(anomalie: Anomalie) -> None:
        anomalies[f"{anomalie.fichier_source}:{anomalie.code_anomalie}"] += 1

    depart = time.perf_counter()
    configuration = LecteurTarifsJson(dossier / "tarifs.json").lire(signaler)
    registre = RegistreAbonnements(
        LecteurAbonnementsJsonl(dossier / "abonnes.jsonl").lire(signaler)
    )
    stations = codes_stations(dossier / "stations.csv")

    moteur = MoteurFacturation(configuration, registre, signaler, stations)
    reel = analyser_recettes(moteur, LecteurTrajetsGzip(dossier / TRAJETS).lire(signaler))

    # Contrefactuel : relecture du flux, anomalies non recomptées.
    ancienne = avec_grille_unique(configuration, date(2025, 1, 1))
    moteur_ancien = MoteurFacturation(ancienne, registre, lambda _: None)
    contrefactuel = analyser_recettes(
        moteur_ancien, LecteurTrajetsGzip(dossier / TRAJETS).lire(lambda _: None)
    )
    ecarts = effet_prix(reel, contrefactuel)
    effet_octobre = sum((v for (m, _), v in ecarts.items() if m == "2026-10"), Decimal(0))

    print(
        json.dumps(
            {
                "recettes_reelles": _tableau(reel),
                "recettes_si_ancienne_grille": _tableau(contrefactuel),
                "effet_prix_octobre_par_formule": {
                    f.value: str(v) for (m, f), v in ecarts.items() if m == "2026-10"
                },
                "effet_prix_octobre_total": str(effet_octobre),
                "economies_plafond_r6": {
                    f"{m}:{f.value}": str(v)
                    for (m, f), v in sorted(reel.economies_plafond.items())
                    if v
                },
                "trajets_par_mois_formule": {
                    f"{m}:{f.value}": n for (m, f), n in sorted(reel.trajets.items())
                },
                "statuts": {s.value: n for s, n in reel.statuts.items()},
                "compteurs_moteur": dict(moteur.compteurs),
                "anomalies_par_code": dict(sorted(anomalies.items())),
                "total_reel": str(reel.total()),
                "temps_secondes": round(time.perf_counter() - depart, 3),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
