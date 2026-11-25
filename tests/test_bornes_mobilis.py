"""Contrat exact de serveur_bornes.py : auth, pages, détails et erreurs."""

import json
import threading
import time
from datetime import UTC, datetime
from email.message import Message
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from mobilis.adapters.bornes_http import _telecharger_octets
from mobilis.adapters.bornes_mobilis import ClientMobilisBornes
from mobilis.services.etat_reseau import EtatBorne, collecter_threads_avec_erreurs


def _erreur_http(code: int) -> HTTPError:
    return HTTPError("http://127.0.0.1:8765/stations/MB-0001", code, "erreur", Message(), None)


def test_header_api_key_reellement_envoye() -> None:
    reponse = Mock()
    reponse.__enter__ = Mock(return_value=reponse)
    reponse.__exit__ = Mock(return_value=None)
    reponse.read.return_value = b"{}"
    with patch("mobilis.adapters.bornes_http.urlopen", return_value=reponse) as ouvrir:
        assert _telecharger_octets("http://127.0.0.1:8765/stations", 3, "test-secret") == b"{}"
    requete: Request = ouvrir.call_args.args[0]
    assert requete.get_header("X-api-key") == "test-secret"
    assert ouvrir.call_args.kwargs["timeout"] == 3


def test_parcours_pages_officielles_et_mapping_borne() -> None:
    urls: list[str] = []

    def lire(url: str, _timeout: float) -> bytes:
        urls.append(url)
        if url.endswith("stations?page=1"):
            donnees: dict[str, object] = {
                "page": 1,
                "stations": ["MB-0001", "MB-0002"],
                "page_suivante": 2,
            }
        elif url.endswith("stations?page=2"):
            donnees = {"page": 2, "stations": ["MB-0003"], "page_suivante": None}
        else:
            donnees = {
                "code": "MB-0001",
                "velos_mecaniques": 2,
                "velos_electriques": 3,
                "places_libres": 7,
                "horodatage": "2026-11-25T10:00:00+00:00",
            }
        return json.dumps(donnees).encode()

    client = ClientMobilisBornes(lire_octets=lire)
    assert client.lister_codes_stations() == ["MB-0001", "MB-0002", "MB-0003"]
    etat = client.lire_etat("MB-0001")
    assert etat == EtatBorne(
        code_station="MB-0001",
        velos_disponibles=5,
        places_libres=7,
        velos_mecaniques=2,
        velos_electriques=3,
        horodatage=datetime(2026, 11, 25, 10, tzinfo=UTC),
    )
    assert urls == [
        "http://127.0.0.1:8765/stations?page=1",
        "http://127.0.0.1:8765/stations?page=2",
        "http://127.0.0.1:8765/stations/MB-0001",
    ]


@pytest.mark.parametrize(
    ("reponse", "message"),
    [
        ({"page": 3, "stations": [], "page_suivante": None}, "page incohérente"),
        ({"page": 1, "stations": "invalid", "page_suivante": None}, "stations"),
        ({"page": 1, "stations": [], "page_suivante": 0}, "page_suivante"),
        ({"page": 1, "stations": [], "page_suivante": 1}, "Boucle"),
    ],
)
def test_pagination_rejette_responses_invalides(reponse: dict[str, object], message: str) -> None:
    client = ClientMobilisBornes(lire_octets=lambda url, timeout: json.dumps(reponse).encode())
    with pytest.raises(ValueError, match=message):
        client.lister_codes_stations()


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("velos_mecaniques", -1),
        ("velos_electriques", True),
        ("places_libres", "3"),
        ("horodatage", "2026-11-25T11:00:00"),
        ("code", "MB-9999"),
    ],
)
def test_mapping_rejette_champs_invalides(champ: str, valeur: object) -> None:
    reponse: dict[str, object] = {
        "code": "MB-0001",
        "velos_mecaniques": 3,
        "velos_electriques": 2,
        "places_libres": 4,
        "horodatage": "2026-11-25T11:00:00+00:00",
    }
    reponse[champ] = valeur
    client = ClientMobilisBornes(lire_octets=lambda url, timeout: json.dumps(reponse).encode())
    with pytest.raises(ValueError):
        client.lire_etat("MB-0001")


def test_401_non_reessayee_avec_mauvaise_cle() -> None:
    appels = 0

    def lire(url: str, timeout: float) -> bytes:
        nonlocal appels
        appels += 1
        raise _erreur_http(401)

    client = ClientMobilisBornes(lire_octets=lire, dormir=lambda sec: None)
    with pytest.raises(HTTPError) as exc:
        client.lister_codes_stations()
    assert exc.value.code == 401
    assert appels == 1


def test_collecte_continue_si_borne_504_et_limite_huit() -> None:
    garde = threading.Lock()
    actifs = 0
    maximum = 0

    def lire_etat(code: str) -> EtatBorne:
        nonlocal actifs, maximum
        with garde:
            actifs += 1
            maximum = max(maximum, actifs)
        time.sleep(0.003)
        with garde:
            actifs -= 1
        if code == "MB-0005":
            raise _erreur_http(504)
        return EtatBorne(code, 2, 10)

    codes = [f"MB-{n:04d}" for n in range(1, 31)]
    resultat = collecter_threads_avec_erreurs(codes, lire_etat, max_simultanes=8)
    assert len(resultat.etats) == 29
    assert list(resultat.erreurs) == ["MB-0005"]
    assert "HTTPError" in resultat.erreurs["MB-0005"]
    assert [etat.code_station for etat in resultat.etats] == [c for c in codes if c != "MB-0005"]
    assert 1 < maximum <= 8


def test_collecte_rejette_plus_de_huit() -> None:
    with pytest.raises(ValueError, match="huit"):
        collecter_threads_avec_erreurs([], lambda code: EtatBorne(code, 1, 1), max_simultanes=9)
