"""Tests HTTP sans serveur et vérification de la borne de concurrence."""

import asyncio
import json
import threading
import time
from datetime import date
from decimal import Decimal
from email.message import Message
from urllib.error import HTTPError

import pytest

from mobilis.adapters.bornes_http import ClientBornesHTTP, reessayer_http
from mobilis.domain.models import Station, StatutStation
from mobilis.services.etat_reseau import (
    EtatBorne,
    collecter_async,
    collecter_sequentiel,
    collecter_threads,
    comparer_etats,
    mesurer_strategies,
)


def _erreur_http(code: int, retry_after: str | None = None) -> HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return HTTPError("http://localhost/api", code, "error", headers, None)


@pytest.mark.parametrize("code", [429, 503, 504])
def test_retry_codes_transitoires(code: int) -> None:
    attentes: list[float] = []
    essais = 0

    def appel() -> int:
        nonlocal essais
        essais += 1
        if essais < 3:
            raise _erreur_http(code, "2" if code == 429 else None)
        return 200

    resultat = reessayer_http(tentatives=3, pause_initiale=0.1, dormir=attentes.append)(
        appel
    )()
    assert resultat == 200
    assert essais == 3
    if code == 429:
        assert attentes == [2.0, 2.0]
    else:
        assert attentes == [0.1, 0.2]


def test_pas_de_retry_sur_404() -> None:
    attentes: list[float] = []

    def appel() -> int:
        raise _erreur_http(404)

    with pytest.raises(HTTPError):
        reessayer_http(dormir=attentes.append)(appel)()
    assert attentes == []


def test_retry_arrete_apres_trois_tentatives() -> None:
    essais = 0

    def appel() -> bytes:
        nonlocal essais
        essais += 1
        raise _erreur_http(503)

    with pytest.raises(HTTPError):
        reessayer_http(tentatives=3, dormir=lambda _: None)(appel)()
    assert essais == 3


def test_client_json_et_pagination_sans_serveur() -> None:
    urls: list[str] = []

    def lire(url: str, timeout: float) -> bytes:
        urls.append(url)
        page = 1 if url.endswith("page=1") else 2
        suivant = "?page=2" if page == 1 else None
        return json.dumps({"items": [{"code": f"MB-{page}"}], "next": suivant}).encode()

    client = ClientBornesHTTP("http://localhost:8080/api/", lire_octets=lire)

    def extraire(doc: object) -> tuple[list[dict[str, object]], str | None]:
        assert isinstance(doc, dict)
        items = doc["items"]
        suivant = doc["next"]
        assert isinstance(items, list)
        assert suivant is None or isinstance(suivant, str)
        return items, suivant

    pages = list(client.iterer_pages("stations?page=1", extraire))
    assert [p["code"] for p in pages] == ["MB-1", "MB-2"]
    assert len(urls) == 2


def test_refuse_pagination_domaine_externe() -> None:
    client = ClientBornesHTTP("https://localhost:8080/")
    with pytest.raises(ValueError, match="hôte externe"):
        client.lire_json("http://evil.example.test/")


def test_approche_threads_limitee_a_huit_requetes() -> None:
    verrou = threading.Lock()
    actifs = 0
    maxi = 0

    def charger(code: str) -> EtatBorne:
        nonlocal actifs, maxi
        with verrou:
            actifs += 1
            maxi = max(maxi, actifs)
        time.sleep(0.004)
        with verrou:
            actifs -= 1
        return EtatBorne(code, 1, 4)

    resultat = collecter_threads((str(i) for i in range(32)), charger)
    assert len(resultat) == 32
    assert 1 < maxi <= 8


def test_asyncio_pont_thread_respecte_egalement_la_limite() -> None:
    verrou = threading.Lock()
    actifs = 0
    maxi = 0

    def charger(code: str) -> EtatBorne:
        nonlocal actifs, maxi
        with verrou:
            actifs += 1
            maxi = max(maxi, actifs)
        time.sleep(0.004)
        with verrou:
            actifs -= 1
        return EtatBorne(code, 1, 4)

    resultat = asyncio.run(collecter_async((str(i) for i in range(25)), charger))
    assert len(resultat) == 25
    assert 1 < maxi <= 8


def test_concurrence_plus_de_huit_refusee() -> None:
    with pytest.raises(ValueError):
        collecter_threads(["MB-01"], lambda code: EtatBorne(code, 1, 1), max_simultanes=9)


def test_rapprochement_stations() -> None:
    stations = [
        Station(
            "MB-1", "A", "Ville", 5, Decimal("49.0"), Decimal("1.0"),
            StatutStation.EN_SERVICE, date(2020, 1, 1),
        ),
        Station(
            "MB-2", "B", "Ville", 5, None, None,
            StatutStation.EN_SERVICE, date(2020, 1, 1),
        ),
        Station(
            "MB-3", "C", "Ville", 5, None, None,
            StatutStation.EN_SERVICE, date(2020, 1, 1),
        ),
    ]
    etats = [
        EtatBorne("MB-1", 0, 5),
        EtatBorne("MB-2", 5, 0),
        EtatBorne("MB-4", 1, 2),
    ]
    resultat = comparer_etats(stations, etats)
    assert resultat.vides == ("MB-1",)
    assert resultat.pleines == ("MB-2",)
    assert resultat.stations_inconnues == ("MB-4",)
    assert resultat.stations_sans_reponse == ("MB-3",)


def test_comparaison_trois_strategies_mesuree() -> None:
    codes = ["MB-1", "MB-2"]
    charger = lambda code: EtatBorne(code, 1, 2)
    assert len(collecter_sequentiel(codes, charger)) == 2
    mesures = mesurer_strategies(codes, charger)
    assert set(mesures) == {"sequentiel", "threads", "asyncio_to_thread"}
    assert all(valeur >= 0 for valeur in mesures.values())
