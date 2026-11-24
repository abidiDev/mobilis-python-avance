"""Benchmark de scalabilité US-02, synthétique, sans modifier les données du kit.

Utilisation :
python scripts/benchmark_trajets.py ../mobilis-kit/donnees/trajets_2026-08_2026-10.csv.gz --facteur 100

IMPORTANT : x100 peut demander beaucoup de temps et plusieurs Go de disque.
Le mode --tracemalloc ajoute du surcoût important ; le pic RSS du processus
est également relevé pour toutes les exécutions.
"""

import argparse
import csv
import gzip
import json
import os
import shutil
import sys
import tempfile
import time
import tracemalloc
from collections import Counter
from pathlib import Path

from mobilis.adapters.trajets_csv import LecteurTrajetsGzip
from mobilis.domain.anomalies import Anomalie
from mobilis.services.frequentation import analyser_frequentation

_GIB = 1024**3


def creer_fichier_synthetique(
    source: Path, cible: Path, *, facteur: int, max_lignes: int | None = None
) -> int:
    """Copier le CSV.gz en flux, avec IDs isolés par répétition.

    Les doublons présents *dans* chaque répétition restent intentionnellement
    des doublons. Les différents blocs, eux, n'ont aucun ID en commun.
    Renvoie le nombre de lignes de données écrites (hors en-tête).
    """
    if not 1 <= facteur <= 100:
        raise ValueError("facteur doit être compris entre 1 et 100")
    if max_lignes is not None and max_lignes < 1:
        raise ValueError("max_lignes doit être positif")
    if source.resolve() == cible.resolve():
        raise ValueError("Le fichier synthétique ne doit pas écraser le fichier source")
    lignes = 0
    with gzip.open(cible, "wt", encoding="utf-8", newline="", compresslevel=1) as sortie:
        writer = csv.writer(sortie)
        for numero in range(facteur):
            with gzip.open(source, "rt", encoding="utf-8-sig", newline="") as entree:
                reader = csv.reader(entree)
                entete = next(reader)
                if numero == 0:
                    writer.writerow(entete)
                for position, ligne in enumerate(reader):
                    if max_lignes is not None and position >= max_lignes:
                        break
                    if not ligne:
                        raise ValueError("Ligne CSV vide dans le fichier source")
                    ligne[0] = f"{ligne[0]}-S{numero:03d}"
                    writer.writerow(ligne)
                    lignes += 1
    return lignes


def _pic_rss_octets() -> int | None:
    """Pic de mémoire résidente du processus (Linux, macOS ou Windows)."""
    if sys.platform == "win32":
        import ctypes

        class CompteursMemoire(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        compteur = CompteursMemoire()
        compteur.cb = ctypes.sizeof(compteur)
        processus = ctypes.windll.kernel32.GetCurrentProcess()
        succes = ctypes.windll.psapi.GetProcessMemoryInfo(
            processus, ctypes.byref(compteur), ctypes.sizeof(compteur)
        )
        return int(compteur.PeakWorkingSetSize) if succes else None
    if sys.platform in {"linux", "darwin"}:
        import resource

        pic = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(pic if sys.platform == "darwin" else pic * 1024)
    return None


def lancer_benchmark(
    source: Path, *, facteur: int = 2, max_lignes: int | None = None,
    tracer_memoire: bool = False, repertoire_temp: Path | None = None
) -> dict[str, object]:
    """Générer un fichier temporaire et mesurer le pipeline réel, puis nettoyer."""
    if not source.is_file():
        raise FileNotFoundError(source)
    if not 1 <= facteur <= 100:
        raise ValueError("facteur doit être compris entre 1 et 100")
    if max_lignes is not None and max_lignes < 1:
        raise ValueError("max_lignes doit être positif")

    racine = repertoire_temp if repertoire_temp is not None else Path(tempfile.gettempdir())
    racine.mkdir(parents=True, exist_ok=True)
    libre = shutil.disk_usage(racine).free
    besoin_estime = max(_GIB, source.stat().st_size * facteur * 20)
    reserve = 2 * _GIB
    if libre < besoin_estime + reserve:
        raise OSError(
            "Espace disque insuffisant pour un benchmark sécurisé : "
            f"{libre / _GIB:.1f} GiB libres, "
            f"{(besoin_estime + reserve) / _GIB:.1f} GiB conseillés."
        )

    with tempfile.TemporaryDirectory(prefix="mobilis-bench-", dir=racine) as repertoire:
        cible = Path(repertoire) / "trajets_synthetiques.csv.gz"
        debut_generation = time.perf_counter()
        lignes = creer_fichier_synthetique(
            source, cible, facteur=facteur, max_lignes=max_lignes
        )
        temps_generation = time.perf_counter() - debut_generation
        anomalies: Counter[str] = Counter()

        def signaler(anomalie: Anomalie) -> None:
            anomalies[anomalie.code_anomalie] += 1

        lecteur = LecteurTrajetsGzip(cible)
        debut_analyse = time.perf_counter()
        pic_tracemalloc: int | None = None
        if tracer_memoire:
            tracemalloc.start()
        try:
            rapport = analyser_frequentation(lecteur.lire(signaler))
            if tracer_memoire:
                _, pic_tracemalloc = tracemalloc.get_traced_memory()
        finally:
            if tracer_memoire:
                tracemalloc.stop()
        temps_analyse = time.perf_counter() - debut_analyse
        return {
            "facteur": facteur,
            "lignes_source_par_copie": lignes // facteur,
            "lignes_synthetiques": lignes,
            "trajets_uniques_valides": rapport.trajets,
            "doublons_identiques": anomalies["DOUBLON_IDENTIQUE"],
            "anomalies_par_code": dict(anomalies),
            "temps_generation_secondes": round(temps_generation, 3),
            "temps_analyse_secondes": round(temps_analyse, 3),
            "pic_tracemalloc_octets": pic_tracemalloc,
            "pic_rss_processus_octets": _pic_rss_octets(),
            "index_sqlite_octets": lecteur.taille_index_octets,
            "fichier_gzip_synthetique_octets": cible.stat().st_size,
            "espace_disque_libre_avant_octets": libre,
            "dossier_temporaire_nettoye_automatiquement": True,
        }


def main() -> None:
    """Lire les arguments et imprimer un rapport JSON exploitable."""
    parser = argparse.ArgumentParser(description="Mobilis — benchmark de scalabilité US-02")
    parser.add_argument("source", type=Path, help="Fichier officiel trajets CSV.gz")
    parser.add_argument("--facteur", type=int, default=2, choices=[1, 2, 10, 100])
    parser.add_argument(
        "--max-lignes", type=int, default=None,
        help="Limiter l'échantillon par copie (pour tests rapides)",
    )
    parser.add_argument(
        "--tracemalloc", action="store_true",
        help="Tracer le pic d'allocations Python, avec ralentissement notable",
    )
    parser.add_argument(
        "--temp-dir", type=Path, default=None,
        help="Répertoire temporaire, de préférence hors dépôt",
    )
    args = parser.parse_args()
    resultat = lancer_benchmark(
        args.source, facteur=args.facteur, max_lignes=args.max_lignes,
        tracer_memoire=args.tracemalloc, repertoire_temp=args.temp_dir
    )
    print(json.dumps(resultat, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
