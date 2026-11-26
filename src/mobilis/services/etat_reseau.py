"""État des stations : collecte concurrente et rapprochement avec le référentiel."""

import asyncio
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import TypeVar

from mobilis.domain.models import EtatBorne, Station

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ResultatCollecte:
    """Réussites et erreurs individuelles d'une collecte réseau."""

    etats: tuple[EtatBorne, ...]
    erreurs: dict[str, str]


@dataclass(frozen=True, slots=True)
class RapportEtat:
    """Bilan instantané de l'état des bornes."""

    vides: tuple[str, ...]
    pleines: tuple[str, ...]
    capacites_incoherentes: tuple[str, ...]
    stations_inconnues: tuple[str, ...]
    stations_sans_reponse: tuple[str, ...]


def collecter_sequentiel(codes: Iterable[str], charger: Callable[[str], T]) -> list[T]:
    """Interroger les stations les unes après les autres."""
    return [charger(code) for code in codes]


def collecter_threads(
    codes: Iterable[str],
    charger: Callable[[str], T],
    *,
    max_simultanes: int = 8,
) -> list[T]:
    """Collecter les stations avec au plus 8 threads E/S."""
    if not 1 <= max_simultanes <= 8:
        raise ValueError("La limite de concurrence doit être comprise entre 1 et 8")
    with ThreadPoolExecutor(max_workers=max_simultanes) as pool:
        return list(pool.map(charger, codes))


async def collecter_async(
    codes: Iterable[str],
    charger: Callable[[str], T],
    *,
    max_simultanes: int = 8,
) -> list[T]:
    """Comparer une orchestration asyncio de travail HTTP synchrone.

    asyncio.to_thread utilise aussi des threads ; cette approche est un pont
    asynchrone et non un client HTTP asynchrone natif. Mentionner cette limite
    dans les benchmarks pour éviter une comparaison trompeuse.
    """
    if not 1 <= max_simultanes <= 8:
        raise ValueError("La limite de concurrence doit être comprise entre 1 et 8")
    semaphore = asyncio.Semaphore(max_simultanes)

    async def charger_une(code: str) -> T:
        async with semaphore:
            return await asyncio.to_thread(charger, code)

    return await asyncio.gather(*(charger_une(code) for code in codes))


def mesurer_strategies(
    codes: Iterable[str],
    charger: Callable[[str], EtatBorne],
    *,
    max_simultanes: int = 8,
) -> dict[str, float]:
    """Mesurer les durées des 3 stratégies sur le même ensemble de codes.

    Les erreurs individuelles de borne (504, connexion, JSON invalide) sont
    ignorées uniquement pour chronométrer *tous* les codes sans interrompre
    le benchmark. Elles ne sont pas converties en faux états métier et
    les résultats de mesure ne sont jamais utilisés dans comparer_etats.
    Répéter les mesures pour comparer les performances sérieusement.
    """
    liste = list(codes)
    mesures: dict[str, float] = {}

    def appeler_pour_mesure(code: str) -> None:
        try:
            charger(code)
        except (OSError, ValueError, TypeError):
            # Le benchmark mesure le coût des échecs, sans inventer de réponse.
            pass

    debut = perf_counter()
    collecter_sequentiel(liste, appeler_pour_mesure)
    mesures["sequentiel"] = perf_counter() - debut

    debut = perf_counter()
    collecter_threads(liste, appeler_pour_mesure, max_simultanes=max_simultanes)
    mesures["threads"] = perf_counter() - debut

    debut = perf_counter()
    asyncio.run(collecter_async(liste, appeler_pour_mesure, max_simultanes=max_simultanes))
    mesures["asyncio_to_thread"] = perf_counter() - debut
    return mesures


def collecter_threads_avec_erreurs(
    codes: Iterable[str],
    charger: Callable[[str], EtatBorne],
    *,
    max_simultanes: int = 8,
) -> ResultatCollecte:
    """Interroger toutes les bornes sans perdre les réussites si l'une échoue.

    Une erreur HTTP, un délai dépassé ou un JSON malformé est rattaché au code
    concerné ; la collecte continue. L'ordre des succès suit celui des codes
    demandés. Avec max_simultanes=8, aucune requête supplémentaire n'est
    démarrée avant qu'un des huit travailleurs soit disponible.
    """
    if not 1 <= max_simultanes <= 8:
        raise ValueError("La limite de concurrence doit être comprise entre 1 et 8")
    liste = list(codes)
    etats_par_position: dict[int, EtatBorne] = {}
    erreurs: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_simultanes) as pool:
        travaux = {
            pool.submit(charger, code): (position, code) for position, code in enumerate(liste)
        }
        for travail in as_completed(travaux):
            position, code = travaux[travail]
            try:
                etats_par_position[position] = travail.result()
            except (OSError, TimeoutError, ValueError, TypeError) as exc:
                erreurs[code] = f"{type(exc).__name__}: {exc}"
    return ResultatCollecte(
        etats=tuple(etats_par_position[pos] for pos in sorted(etats_par_position)),
        erreurs=erreurs,
    )


def comparer_etats(stations: Iterable[Station], etats: Iterable[EtatBorne]) -> RapportEtat:
    """Comparer les compteurs du serveur aux capacités du référentiel.

    Ne pas inventer de données pour les stations sans réponse. Le contrôle
    suppose un référentiel déjà validé et dédoublonné par US-01.
    """
    references = {station.code: station for station in stations}
    recus: set[str] = set()
    vides: set[str] = set()
    pleines: set[str] = set()
    capacites: set[str] = set()
    inconnues: set[str] = set()
    for etat in etats:
        code = etat.code_station
        recus.add(code)
        if code not in references:
            inconnues.add(code)
            continue
        if etat.velos_disponibles < 0 or etat.places_libres < 0:
            capacites.add(code)
            continue
        if etat.velos_disponibles == 0:
            vides.add(code)
        if etat.places_libres == 0:
            pleines.add(code)
        capacite = references[code].capacite
        if capacite is not None and etat.velos_disponibles + etat.places_libres != capacite:
            capacites.add(code)

    return RapportEtat(
        vides=tuple(sorted(vides)),
        pleines=tuple(sorted(pleines)),
        capacites_incoherentes=tuple(sorted(capacites)),
        stations_inconnues=tuple(sorted(inconnues)),
        stations_sans_reponse=tuple(sorted(set(references) - recus)),
    )
