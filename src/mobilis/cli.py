"""Interface en ligne de commande `mobilis` : orchestre adaptateurs et services.

    mobilis stations      référentiel des stations et anomalies
    mobilis frequentation profils horaires et soldes matin/soir des stations
    mobilis facturation   recettes mensuelles et effet du 1er octobre 2026
    mobilis etat          état temps réel des bornes (simulateur HTTP)

Les données du kit ne sont pas versionnées : leur dossier se donne par
`--donnees` ou par la variable d'environnement MOBILIS_DONNEES.

Codes de sortie : 0 succès, 1 données absentes ou invalides,
2 usage incorrect (argparse), 3 API des bornes injoignable.
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from mobilis.adapters.abonnes_jsonl import LecteurAbonnementsJsonl
from mobilis.adapters.bornes_mobilis import ClientMobilisBornes
from mobilis.adapters.stations_csv import LecteurStationsCsv
from mobilis.adapters.tarifs_json import LecteurTarifsJson, TarifsInvalides
from mobilis.adapters.trajets_csv import LecteurTrajetsGzip
from mobilis.domain.anomalies import Anomalie, CollecteurAnomalies
from mobilis.domain.models import EtatBorne
from mobilis.services.etat_reseau import (
    collecter_threads_avec_erreurs,
    comparer_etats,
    mesurer_strategies,
)
from mobilis.services.facturation import MoteurFacturation, RegistreAbonnements
from mobilis.services.frequentation import analyser_avec_pic_memoire, analyser_frequentation
from mobilis.services.recettes import (
    RapportRecettes,
    analyser_recettes,
    avec_grille_unique,
    effet_prix,
)
from mobilis.services.stations import RapportStations, construire_referentiel

FICHIERS = {
    "stations": "stations.csv",
    "trajets": "trajets_2026-08_2026-10.csv.gz",
    "abonnes": "abonnes.jsonl",
    "tarifs": "tarifs.json",
}
SUCCES, ERREUR_DONNEES, ERREUR_API = 0, 1, 3

Bornes = tuple[list[str], Callable[[str], EtatBorne]]


class ErreurDonnees(Exception):
    """Fichier absent ou illisible : message clair et code de sortie 1."""


# --- Utilitaires ---------------------------------------------------------------


def _chemin(args: argparse.Namespace, nom: str) -> Path:
    """Fichier explicite (--stations…) sinon dossier --donnees / MOBILIS_DONNEES."""
    explicite: Path | None = getattr(args, nom, None)
    if explicite is not None:
        chemin = explicite
    else:
        dossier = args.donnees or os.environ.get("MOBILIS_DONNEES")
        if not dossier:
            raise ErreurDonnees(
                "dossier des données inconnu : utiliser --donnees DOSSIER "
                "ou la variable d'environnement MOBILIS_DONNEES"
            )
        chemin = Path(dossier) / FICHIERS[nom]
    if not chemin.is_file():
        raise ErreurDonnees(f"fichier introuvable : {chemin}")
    return chemin


def _ecrire_journal(chemin: Path | None, anomalies: Sequence[Anomalie]) -> None:
    """Exporter le journal détaillé en CSV UTF-8 (une ligne par anomalie)."""
    if chemin is None:
        return
    with chemin.open("w", encoding="utf-8", newline="") as flux:
        ecrivain = csv.writer(flux, delimiter=";")
        ecrivain.writerow(
            [
                "fichier_source",
                "ligne",
                "identifiant",
                "champ",
                "code_anomalie",
                "niveau",
                "valeur_observee",
                "traitement_propose",
            ]
        )
        for a in anomalies:
            ecrivain.writerow(
                [
                    a.fichier_source,
                    "" if a.ligne is None else a.ligne,
                    a.identifiant,
                    a.champ,
                    a.code_anomalie,
                    a.niveau.value,
                    a.valeur_observee,
                    a.traitement_propose,
                ]
            )


def _compter(anomalies: Sequence[Anomalie]) -> dict[str, int]:
    return dict(sorted(Counter(f"{a.fichier_source}:{a.code_anomalie}" for a in anomalies).items()))


def euros(montant: Decimal) -> str:
    """`Decimal("62954.05")` → `"62 954,05 €"`."""
    signe = "-" if montant < 0 else ""
    entier, _, centimes = f"{abs(montant):.2f}".partition(".")
    milliers = f"{int(entier):,}".replace(",", " ")
    return f"{signe}{milliers},{centimes} €"


def _sortir(resultat: dict[str, Any], args: argparse.Namespace, texte: Callable[[], str]) -> None:
    if args.json:
        print(json.dumps(resultat, ensure_ascii=False, indent=2, default=str))
    else:
        print(texte())


def _referentiel(args: argparse.Namespace, journal: CollecteurAnomalies) -> RapportStations:
    lecteur = LecteurStationsCsv(_chemin(args, "stations"))
    return construire_referentiel(lecteur.lire(journal.signaler), journal.signaler)


def _rien(_: Anomalie) -> None:
    """Le contrefactuel relit les mêmes données : ses anomalies sont déjà comptées."""


# --- Commandes -----------------------------------------------------------------


def commande_stations(args: argparse.Namespace) -> int:
    journal = CollecteurAnomalies()
    rapport = _referentiel(args, journal)
    _ecrire_journal(args.journal, journal.elements)
    anomalies = _compter(journal.elements)
    resultat = {
        "versions_lues": rapport.versions_lues,
        "stations": len(rapport.referentiel),
        "exploitables": len(rapport.exploitables),
        "par_statut": {s.value: n for s, n in sorted(rapport.par_statut().items())},
        "non_exploitables": rapport.non_exploitables,
        "anomalies": anomalies,
    }

    def texte() -> str:
        return "\n".join(
            [
                f"Versions lues : {rapport.versions_lues}",
                f"Stations du référentiel : {len(rapport.referentiel)}",
                f"Stations exploitables : {len(rapport.exploitables)}",
                "Non exploitables :",
                *(f"  {code} — {motif}" for code, motif in rapport.non_exploitables.items()),
                "Anomalies :",
                *(f"  {code} : {n}" for code, n in anomalies.items()),
            ]
        )

    _sortir(resultat, args, texte)
    return SUCCES


def commande_frequentation(args: argparse.Namespace) -> int:
    journal = CollecteurAnomalies()
    debut = time.perf_counter()
    trajets = LecteurTrajetsGzip(_chemin(args, "trajets")).lire(journal.signaler)
    pic: int | None = None
    if args.memoire:
        rapport, pic = analyser_avec_pic_memoire(trajets)
    else:
        rapport = analyser_frequentation(trajets)
    duree = time.perf_counter() - debut
    _ecrire_journal(args.journal, journal.elements)
    anomalies = _compter(journal.elements)
    flux = rapport.flux_stations.items()
    matin = [(c, f.solde_matin) for c, f in sorted(flux, key=lambda kv: kv[1].solde_matin)]
    soir = [(c, f.solde_soir) for c, f in sorted(flux, key=lambda kv: -kv[1].solde_soir)]
    profils = {
        "semaine": [rapport.profils_departs.get((False, h), 0) for h in range(24)],
        "week-end": [rapport.profils_departs.get((True, h), 0) for h in range(24)],
    }
    resultat = {
        "trajets": rapport.trajets,
        "sans_retour": rapport.sans_retour,
        "se_vident_le_matin": matin[: args.top],
        "se_remplissent_le_soir": soir[: args.top],
        "departs_par_heure": profils,
        "pic_tracemalloc_octets": pic,
        "duree_secondes": round(duree, 3),
        "anomalies": anomalies,
    }

    def texte() -> str:
        maximum = max(*profils["semaine"], *profils["week-end"], 1)
        lignes = [
            f"Trajets uniques : {rapport.trajets} (dont {rapport.sans_retour} sans retour)",
            "Stations qui se vident le matin (07h-10h, arrivées - départs) :",
            *(f"  {c} : {s:+d}" for c, s in matin[: args.top]),
            "Stations qui se remplissent le soir (17h-20h) :",
            *(f"  {c} : {s:+d}" for c, s in soir[: args.top]),
            "Départs par heure (Europe/Paris)  semaine  week-end",
        ]
        for h in range(24):
            sem, we = profils["semaine"][h], profils["week-end"][h]
            lignes.append(f"  {h:02d}h {sem:>9} {we:>9}  {'#' * round(30 * sem / maximum)}")
        lignes += [
            f"Durée : {duree:.1f} s"
            + ("" if pic is None else f" ; pic tracemalloc : {pic} octets"),
            "Anomalies :",
            *(f"  {code} : {n}" for code, n in anomalies.items()),
        ]
        return "\n".join(lignes)

    _sortir(resultat, args, texte)
    return SUCCES


def _tableau(rapport: RapportRecettes) -> dict[str, dict[str, str]]:
    tableau: dict[str, dict[str, str]] = {}
    for (mois, formule), montant in sorted(rapport.recettes.items()):
        tableau.setdefault(mois, {})[formule.value] = str(montant)
    for mois, ligne in tableau.items():
        ligne["total"] = str(rapport.total_mois(mois))
    return tableau


def commande_facturation(args: argparse.Namespace) -> int:
    journal = CollecteurAnomalies()
    try:
        configuration = LecteurTarifsJson(_chemin(args, "tarifs")).lire(journal.signaler)
    except TarifsInvalides as exc:
        raise ErreurDonnees(f"tarifs invalides : {exc}") from exc
    registre = RegistreAbonnements(
        LecteurAbonnementsJsonl(_chemin(args, "abonnes")).lire(journal.signaler)
    )
    stations = {s.code for s in _referentiel(args, journal).referentiel}
    trajets = _chemin(args, "trajets")

    moteur = MoteurFacturation(configuration, registre, journal.signaler, stations)
    reel = analyser_recettes(moteur, LecteurTrajetsGzip(trajets).lire(journal.signaler))
    ancienne = configuration.grilles[0].en_vigueur_du
    contrefactuel = analyser_recettes(
        MoteurFacturation(avec_grille_unique(configuration, ancienne), registre, _rien),
        LecteurTrajetsGzip(trajets).lire(_rien),
    )
    _ecrire_journal(args.journal, journal.elements)

    effet: dict[str, Decimal] = {}
    for (mois, _), ecart in effet_prix(reel, contrefactuel).items():
        effet[mois] = effet.get(mois, Decimal("0.00")) + ecart
    anomalies = _compter(journal.elements)
    resultat = {
        "recettes": _tableau(reel),
        "recettes_ancienne_grille": _tableau(contrefactuel),
        "effet_prix_par_mois": {m: str(v) for m, v in sorted(effet.items())},
        "total": str(reel.total()),
        "statuts": {s.value: n for s, n in reel.statuts.items()},
        "compteurs": dict(moteur.compteurs),
        "anomalies": anomalies,
    }

    def texte() -> str:
        formules = sorted({f for _, f in reel.recettes})
        lignes = [
            "Recettes mensuelles par formule",
            "Mois    " + "".join(f"{f.value:>15}" for f in formules) + f"{'total':>15}",
        ]
        for mois in sorted({m for m, _ in reel.recettes}):
            cellules = "".join(
                f"{euros(reel.recettes.get((mois, f), Decimal('0.00'))):>15}" for f in formules
            )
            lignes.append(f"{mois} {cellules}{euros(reel.total_mois(mois)):>15}")
        lignes.append(f"Total du trimestre : {euros(reel.total())}")
        nouvelle = configuration.grilles[-1].en_vigueur_du.isoformat()
        lignes.append(f"Effet prix de la grille du {nouvelle} (mêmes trajets, ancienne grille) :")
        for mois, ecart in sorted(effet.items()):
            base = contrefactuel.total_mois(mois)
            taux = f" ({100 * ecart / base:+.1f} %)".replace(".", ",") if base else ""
            lignes.append(f"  {mois} : {euros(ecart)}{taux}")
        lignes.append("Statuts : " + ", ".join(f"{s.value} {n}" for s, n in reel.statuts.items()))
        lignes += ["Anomalies :", *(f"  {c} : {n}" for c, n in anomalies.items())]
        return "\n".join(lignes)

    _sortir(resultat, args, texte)
    return SUCCES


def ouvrir_bornes(args: argparse.Namespace) -> Bornes:
    """Lister les bornes ; remplaçable dans les tests (aucun serveur lancé)."""
    client = ClientMobilisBornes(args.base_url, api_key=args.api_key)
    return client.lister_codes_stations(), client.lire_etat


def commande_etat(args: argparse.Namespace) -> int:
    journal = CollecteurAnomalies()
    referentiel = _referentiel(args, journal)
    debut = time.perf_counter()
    try:
        codes, lire_etat = ouvrir_bornes(args)
    except (OSError, TimeoutError, ValueError) as exc:
        print(
            f"mobilis: API des bornes injoignable ({args.base_url}) : {exc}\n"
            "Lancer d'abord : python outils/serveur_bornes.py",
            file=sys.stderr,
        )
        return ERREUR_API
    collecte = collecter_threads_avec_erreurs(codes, lire_etat, max_simultanes=args.max_simultanes)
    duree = time.perf_counter() - debut
    # Référentiel complet : une station hors service reste connue (pas « inconnue »).
    rapport = comparer_etats(referentiel.referentiel, collecte.etats)
    exploitables = {s.code for s in referentiel.exploitables}
    sans_reponse = [c for c in rapport.stations_sans_reponse if c in exploitables]
    _ecrire_journal(args.journal, journal.elements)
    resultat: dict[str, Any] = {
        "bornes_listees": len(codes),
        "reponses": len(collecte.etats),
        "erreurs": collecte.erreurs,
        "vides": list(rapport.vides),
        "pleines": list(rapport.pleines),
        "capacites_incoherentes": list(rapport.capacites_incoherentes),
        "inconnues_du_referentiel": list(rapport.stations_inconnues),
        "exploitables_sans_reponse": sans_reponse,
        "duree_secondes": round(duree, 3),
        "moins_de_15_secondes": duree < 15,
    }
    if args.comparer_strategies:
        mesures = mesurer_strategies(codes, lire_etat, max_simultanes=args.max_simultanes)
        resultat["strategies_secondes"] = {nom: round(t, 3) for nom, t in mesures.items()}

    def liste(codes_station: Sequence[str], limite: int = 12) -> str:
        suite = ", …" if len(codes_station) > limite else ""
        return f"({len(codes_station)}) " + (", ".join(codes_station[:limite]) or "-") + suite

    def texte() -> str:
        lignes = [
            f"Bornes interrogées : {len(codes)} ; réponses : {len(collecte.etats)}",
            f"Durée de collecte : {duree:.1f} s",
            f"Vides {liste(rapport.vides)}",
            f"Pleines {liste(rapport.pleines)}",
            f"Capacité différente du référentiel {liste(rapport.capacites_incoherentes)}",
            f"Inconnues du référentiel {liste(rapport.stations_inconnues)}",
            f"Exploitables sans réponse {liste(sans_reponse)}",
        ]
        if collecte.erreurs:
            lignes.append("Erreurs : " + "; ".join(f"{c} {e}" for c, e in collecte.erreurs.items()))
        if "strategies_secondes" in resultat:
            lignes.append(f"Stratégies (s) : {resultat['strategies_secondes']}")
        return "\n".join(lignes)

    _sortir(resultat, args, texte)
    return SUCCES


# --- Analyse des arguments -----------------------------------------------------


def construire_parseur() -> argparse.ArgumentParser:
    commun = argparse.ArgumentParser(add_help=False)
    commun.add_argument(
        "--donnees", type=Path, help="Dossier des fichiers du kit (sinon MOBILIS_DONNEES)"
    )
    commun.add_argument("--json", action="store_true", help="Sortie JSON complète")
    commun.add_argument("--journal", type=Path, help="Exporter le journal des anomalies (CSV)")
    commun.add_argument("--stations", type=Path, help="Chemin explicite de stations.csv")

    parseur = argparse.ArgumentParser(prog="mobilis", description="Analyses du réseau Mobilis")
    parseur.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    sous = parseur.add_subparsers(dest="commande", required=True, metavar="COMMANDE")

    p = sous.add_parser("stations", parents=[commun], help="Référentiel des stations")
    p.set_defaults(executer=commande_stations)

    p = sous.add_parser("frequentation", parents=[commun], help="Fréquentation des stations")
    p.add_argument("--trajets", type=Path, help="Chemin explicite du CSV.gz des trajets")
    p.add_argument("--top", type=int, default=5, help="Nombre de stations affichées")
    p.add_argument("--memoire", action="store_true", help="Mesurer le pic tracemalloc (plus lent)")
    p.set_defaults(executer=commande_frequentation)

    p = sous.add_parser("facturation", parents=[commun], help="Recettes et changement tarifaire")
    p.add_argument("--trajets", type=Path)
    p.add_argument("--abonnes", type=Path)
    p.add_argument("--tarifs", type=Path)
    p.set_defaults(executer=commande_facturation)

    p = sous.add_parser("etat", parents=[commun], help="État temps réel des bornes")
    p.add_argument("--base-url", default="http://127.0.0.1:8765/")
    p.add_argument("--api-key", default=os.environ.get("MOBILIS_API_KEY", "demo-mobilis-2026"))
    p.add_argument("--max-simultanes", type=int, default=8, choices=range(1, 9), metavar="1-8")
    p.add_argument(
        "--comparer-strategies",
        action="store_true",
        help="Mesurer séquentiel / threads / asyncio (serveur lancé avec --calme)",
    )
    p.set_defaults(executer=commande_etat)
    return parseur


def main(argv: Sequence[str] | None = None) -> int:
    args = construire_parseur().parse_args(argv)
    commande: Callable[[argparse.Namespace], int] = args.executer
    try:
        return commande(args)
    except ErreurDonnees as exc:
        print(f"mobilis: {exc}", file=sys.stderr)
        return ERREUR_DONNEES


if __name__ == "__main__":
    sys.exit(main())
