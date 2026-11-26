"""Mesure reproductible de l'US-02 à partir d'un export CSV.gz non versionné.

Exécution après installation locale du paquet :
python scripts/mesurer_frequentation.py ../mobilis-kit/donnees/trajets_2026-08_2026-10.csv.gz
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from mobilis.adapters.trajets_csv import LecteurTrajetsGzip
from mobilis.domain.anomalies import Anomalie
from mobilis.services.frequentation import analyser_avec_pic_memoire


def main() -> None:
    """Imprimer les statistiques du fichier, les anomalies et le pic de mémoire."""
    analyseur = argparse.ArgumentParser(description="Mobilis — mesure fréquentation")
    analyseur.add_argument("trajets", type=Path, help="Chemin vers le CSV.gz non versionné")
    options = analyseur.parse_args()
    anomalies: Counter[str] = Counter()

    def signaler(anomalie: Anomalie) -> None:
        anomalies[anomalie.code_anomalie] += 1

    lecteur = LecteurTrajetsGzip(options.trajets)
    rapport, pic = analyser_avec_pic_memoire(lecteur.lire(signaler))
    stations_matinales = sorted(
        ((code, flux.solde_matin) for code, flux in rapport.flux_stations.items()),
        key=lambda valeur: valeur[1],
    )
    stations_soir = sorted(
        ((code, flux.solde_soir) for code, flux in rapport.flux_stations.items()),
        key=lambda valeur: valeur[1],
        reverse=True,
    )

    print(
        json.dumps(
            {
                "trajets_uniques_valides": rapport.trajets,
                "sans_retour": rapport.sans_retour,
                "pic_memoire_python_octets": pic,
                "anomalies_par_code": dict(anomalies),
                "stations_se_vidant_matin": stations_matinales[:5],
                "stations_se_remplissant_soir": stations_soir[:5],
                "provenance": str(options.trajets),
                "conventions": {
                    "matin": "07:00 à 09:59 Europe/Paris",
                    "soir": "17:00 à 19:59 Europe/Paris",
                    "deduplication": "première ligne valide par trajet_id, index SQLite temporaire",
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
