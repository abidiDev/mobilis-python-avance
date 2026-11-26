"""Construction du référentiel des stations et identification des stations exploitables."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from mobilis.domain.anomalies import Anomalie, NiveauAnomalie, SignalerAnomalie
from mobilis.domain.models import Station, StatutStation

_SOURCE = "referentiel_stations"


@dataclass(frozen=True, slots=True)
class RapportStations:
    """Référentiel dédoublonné : une station par code."""

    versions_lues: int
    referentiel: tuple[Station, ...]
    versions_remplacees: tuple[Station, ...]
    exploitables: tuple[Station, ...]
    non_exploitables: dict[str, str]  # code -> motif

    def par_statut(self) -> dict[StatutStation, int]:
        return dict(Counter(station.statut for station in self.referentiel))


def motif_non_exploitable(station: Station) -> str | None:
    """Une station est exploitable si elle est en service et de capacité connue.

    La capacité est indispensable pour comparer les compteurs des bornes (US-04)
    et détecter une station pleine ; des coordonnées absentes ne l'empêchent pas.
    """
    if not station.en_service:
        return f"statut {station.statut.value}"
    if station.capacite is None:
        return "capacité inconnue"
    return None


def construire_referentiel(
    stations: Iterable[Station], signaler: SignalerAnomalie
) -> RapportStations:
    """Garder, pour chaque code, la version la plus récemment mise en service.

    Un code répété correspond à une station réaménagée (nouvelle capacité,
    remise en service) : la version la plus récente décrit l'état actuel.
    À date égale, la première version lue est conservée.
    """
    retenues: dict[str, Station] = {}
    remplacees: list[Station] = []
    lues = 0
    for station in stations:
        lues += 1
        actuelle = retenues.get(station.code)
        if actuelle is None:
            retenues[station.code] = station
            continue
        recente, ancienne = (
            (station, actuelle)
            if station.mise_en_service > actuelle.mise_en_service
            else (actuelle, station)
        )
        retenues[station.code] = recente
        remplacees.append(ancienne)
        signaler(
            Anomalie(
                _SOURCE,
                None,
                station.code,
                "Code station",
                "CODE_REPETE",
                NiveauAnomalie.ALERTE,
                f"versions du {ancienne.mise_en_service} et du {recente.mise_en_service}",
                f"Version du {recente.mise_en_service} retenue, l'autre est archivée",
            )
        )

    referentiel = tuple(sorted(retenues.values(), key=lambda s: s.code))
    non_exploitables = {
        s.code: motif for s in referentiel if (motif := motif_non_exploitable(s)) is not None
    }
    return RapportStations(
        versions_lues=lues,
        referentiel=referentiel,
        versions_remplacees=tuple(remplacees),
        exploitables=tuple(s for s in referentiel if s.code not in non_exploitables),
        non_exploitables=non_exploitables,
    )
