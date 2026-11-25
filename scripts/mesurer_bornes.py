"""Recette de l'US-04 contre le serveur officiel outils/serveur_bornes.py.

Terminal 1 : python ../mobilis-kit/outils/serveur_bornes.py
Terminal 2 : python scripts/mesurer_bornes.py
"""

import argparse
import json
import os
from collections import Counter
from time import perf_counter

from mobilis.adapters.bornes_mobilis import ClientMobilisBornes
from mobilis.services.etat_reseau import (
    collecter_threads_avec_erreurs,
    mesurer_strategies,
)


def main() -> None:
    """Collecter les stations du simulateur et imprimer la recette en JSON."""
    parser = argparse.ArgumentParser(description="Mobilis — recette état temps réel")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765/")
    parser.add_argument("--api-key", default=os.getenv("MOBILIS_API_KEY", "demo-mobilis-2026"))
    parser.add_argument("--max-simultanes", type=int, default=8)
    parser.add_argument(
        "--comparer-strategies",
        action="store_true",
        help="Mesurer séquentiel/threads/asyncio (démarrer le serveur avec --calme)",
    )
    args = parser.parse_args()
    client = ClientMobilisBornes(args.base_url, api_key=args.api_key)
    debut = perf_counter()
    codes = client.lister_codes_stations()
    temps_liste = perf_counter() - debut
    debut_collecte = perf_counter()
    resultat = collecter_threads_avec_erreurs(
        codes, client.lire_etat, max_simultanes=args.max_simultanes
    )
    temps_collecte = perf_counter() - debut_collecte
    temps_total = perf_counter() - debut
    etats = resultat.etats
    rapport: dict[str, object] = {
        "stations_listees": len(codes),
        "reponses_valides": len(etats),
        "stations_en_erreur": len(resultat.erreurs),
        "stations_vides": sorted(e.code_station for e in etats if e.velos_disponibles == 0),
        "stations_pleines": sorted(e.code_station for e in etats if e.places_libres == 0),
        "velos_disponibles_total": sum(e.velos_disponibles for e in etats),
        "velos_mecaniques_total": sum(e.velos_mecaniques or 0 for e in etats),
        "velos_electriques_total": sum(e.velos_electriques or 0 for e in etats),
        "places_libres_total": sum(e.places_libres for e in etats),
        "erreurs_par_station": resultat.erreurs,
        "erreurs_par_type": dict(Counter(val.split(":", 1)[0] for val in resultat.erreurs.values())),
        "duree_liste_secondes": round(temps_liste, 3),
        "duree_collecte_secondes": round(temps_collecte, 3),
        "duree_totale_secondes": round(temps_total, 3),
        "objectif_moins_15_secondes": temps_total < 15,
        "collecte_complete": len(resultat.erreurs) == 0,
        "limite_concurrence": args.max_simultanes,
        "referentiel_stations": "Rapprochement CSV prévu via US-01 (non intégré ici)",
    }
    if args.comparer_strategies:
        rapport["mesures_strategies_secondes"] = {
            nom: round(temps, 3)
            for nom, temps in mesurer_strategies(
                codes, client.lire_etat, max_simultanes=args.max_simultanes
            ).items()
        }
        rapport["note_comparaison"] = (
            "Trois passages successifs ; même serveur et mêmes codes, "
            "mais les stocks peuvent évoluer entre passages."
        )
    print(json.dumps(rapport, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
