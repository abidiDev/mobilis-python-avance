"""Recette reproductible de l'US-01 (stations) sur le fichier brut du kit.

Commande provisoire en attendant `mobilis stations` (#19) :
python scripts/mesurer_stations.py ../mobilis-kit/donnees/stations.csv
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from mobilis.adapters.stations_csv import LecteurStationsCsv
from mobilis.domain.anomalies import CollecteurAnomalies
from mobilis.services.stations import construire_referentiel


def main() -> None:
    parser = argparse.ArgumentParser(description="Mobilis — recette stations US-01")
    parser.add_argument("stations", type=Path, help="Chemin de stations.csv (non versionné)")
    chemin = parser.parse_args().stations

    journal = CollecteurAnomalies()
    rapport = construire_referentiel(
        LecteurStationsCsv(chemin).lire(journal.signaler), journal.signaler
    )
    anomalies = Counter((a.code_anomalie, a.niveau.value) for a in journal.elements)
    print(
        json.dumps(
            {
                "versions_lues": rapport.versions_lues,
                "stations_referentiel": len(rapport.referentiel),
                "stations_exploitables": len(rapport.exploitables),
                "par_statut": {s.value: n for s, n in rapport.par_statut().items()},
                "non_exploitables": rapport.non_exploitables,
                "codes_repetes": sorted({s.code for s in rapport.versions_remplacees}),
                "anomalies": {f"{code} ({niveau})": n for (code, niveau), n in anomalies.items()},
                "lignes_concernees": {
                    code: sorted(
                        {a.identifiant for a in journal.elements if a.code_anomalie == code}
                    )
                    for code, _ in anomalies
                    if code not in ("STATUT_NON_NORMALISE",)
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
