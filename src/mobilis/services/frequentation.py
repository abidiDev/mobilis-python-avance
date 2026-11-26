"""Agrégations en flux des trajets, sans stocker les trajets en mémoire."""

import tracemalloc
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from mobilis.domain.models import Trajet

_PARIS = ZoneInfo("Europe/Paris")


@dataclass(frozen=True, slots=True)
class FluxStation:
    """Flux directionnels d'une station ; solde positif = vélos entrants."""

    departs_matin: int
    arrivees_matin: int
    departs_soir: int
    arrivees_soir: int

    @property
    def solde_matin(self) -> int:
        return self.arrivees_matin - self.departs_matin

    @property
    def solde_soir(self) -> int:
        return self.arrivees_soir - self.departs_soir


@dataclass(frozen=True, slots=True)
class RapportFrequentation:
    """Résultat agrégé, dont la taille dépend des stations et heures, pas des trajets."""

    trajets: int
    sans_retour: int
    profils_departs: dict[tuple[bool, int], int]
    profils_arrivees: dict[tuple[bool, int], int]
    flux_stations: dict[str, FluxStation]


def _periode(instant: datetime) -> str | None:
    heure = instant.astimezone(_PARIS).hour
    if 7 <= heure < 10:
        return "matin"
    if 17 <= heure < 20:
        return "soir"
    return None


def _weekend(instant: datetime) -> bool:
    return instant.astimezone(_PARIS).weekday() >= 5


def analyser_frequentation(trajets: Iterable[Trajet]) -> RapportFrequentation:
    """Compter départs/arrivées, profils horaires et soldes matin/soir.

    Fenêtres conventionnelles : matin [07h,10h[ et soir [17h,20h[
    dans le fuseau Europe/Paris ; les autres heures restent comptées dans
    les profils horaires. Une arrivée absente n'est pas inventée.
    """
    departs: Counter[tuple[bool, int]] = Counter()
    arrivees: Counter[tuple[bool, int]] = Counter()
    flux: Counter[tuple[str, str, str]] = Counter()
    nb = 0
    sans_retour = 0

    for trajet in trajets:
        nb += 1
        debut_local = trajet.debut.astimezone(_PARIS)
        departs[(_weekend(trajet.debut), debut_local.hour)] += 1
        periode = _periode(trajet.debut)
        if periode is not None:
            flux[(trajet.station_depart, "depart", periode)] += 1

        if trajet.fin is None or trajet.station_arrivee is None:
            sans_retour += 1
            continue

        fin_local = trajet.fin.astimezone(_PARIS)
        arrivees[(_weekend(trajet.fin), fin_local.hour)] += 1
        periode_arrivee = _periode(trajet.fin)
        if periode_arrivee is not None:
            flux[(trajet.station_arrivee, "arrivee", periode_arrivee)] += 1

    codes = {code for code, _, _ in flux}
    stations = {
        code: FluxStation(
            departs_matin=flux[(code, "depart", "matin")],
            arrivees_matin=flux[(code, "arrivee", "matin")],
            departs_soir=flux[(code, "depart", "soir")],
            arrivees_soir=flux[(code, "arrivee", "soir")],
        )
        for code in codes
    }
    return RapportFrequentation(
        trajets=nb,
        sans_retour=sans_retour,
        profils_departs=dict(departs),
        profils_arrivees=dict(arrivees),
        flux_stations=stations,
    )


def analyser_avec_pic_memoire(trajets: Iterable[Trajet]) -> tuple[RapportFrequentation, int]:
    """Analyser les trajets et retourner le pic tracemalloc en octets."""
    tracemalloc.start()
    try:
        rapport = analyser_frequentation(trajets)
        _, pic = tracemalloc.get_traced_memory()
        return rapport, pic
    finally:
        tracemalloc.stop()
