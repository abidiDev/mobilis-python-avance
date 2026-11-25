"""Client HTTP sortant : authentification, retries et pagination.

Le simulateur Mobilis (kit PYA-701) utilise la clé dans X-Api-Key.
L'API particulière et son schéma de réponse sont intégrés dans
bornes_mobilis.py, en conservant cet adaptateur HTTP injectable.
"""

import json
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import wraps
from typing import ParamSpec, TypeVar
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

P = ParamSpec("P")
R = TypeVar("R")

_CODES_REESSAI = frozenset((429, 503, 504))


def _delai_retry_after(valeur: str | None) -> float | None:
    if valeur is None:
        return None
    try:
        return max(0.0, float(valeur))
    except ValueError:
        try:
            date_serveur = parsedate_to_datetime(valeur)
        except (TypeError, ValueError, IndexError):
            return None
        if date_serveur.tzinfo is None:
            return None
        return max(0.0, (date_serveur - datetime.now(UTC)).total_seconds())


def reessayer_http(
    *,
    tentatives: int = 3,
    pause_initiale: float = 0.1,
    dormir: Callable[[float], None] = time.sleep,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Décorateur réutilisable : réessayer uniquement 429, 503 et 504.

    Retry-After a priorité s'il demande une attente plus longue que le backoff.
    On ne réessaie jamais indéfiniment ni pour des erreurs permanentes.
    """
    if tentatives < 1 or pause_initiale < 0:
        raise ValueError("tentatives >= 1 et pause_initiale >= 0 requis")

    def decorer(fonction: Callable[P, R]) -> Callable[P, R]:
        @wraps(fonction)
        def enveloppe(*args: P.args, **kwargs: P.kwargs) -> R:
            for numero in range(tentatives):
                try:
                    return fonction(*args, **kwargs)
                except HTTPError as exc:
                    if exc.code not in _CODES_REESSAI or numero == tentatives - 1:
                        raise
                    delai = _delai_retry_after(exc.headers.get("Retry-After"))
                    dormir(max(pause_initiale * (2**numero), delai or 0.0))
            raise AssertionError("boucle de réessai non terminée")

        return enveloppe

    return decorer


def _telecharger_octets(url: str, timeout: float, api_key: str | None = None) -> bytes:
    entetes = {"Accept": "application/json"}
    if api_key is not None:
        entetes["X-Api-Key"] = api_key
    requete = Request(url, headers=entetes)
    with urlopen(requete, timeout=timeout) as reponse:
        octets: bytes = reponse.read()
        return octets


def _url_sure(base: str, chemin: str) -> str:
    url = urljoin(base, chemin)
    ref = urlparse(base)
    dest = urlparse(url)
    if (ref.scheme, ref.netloc) != (dest.scheme, dest.netloc):
        raise ValueError("pagination vers un hôte externe interdite")
    return url


class ClientBornesHTTP:
    """Lecture de JSON externe, transport injectable pour les tests sans serveur."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 5.0,
        tentatives: int = 3,
        pause_initiale: float = 0.1,
        lire_octets: Callable[[str, float], bytes] = _telecharger_octets,
        dormir: Callable[[float], None] = time.sleep,
        api_key: str | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout doit être positif")
        self.base_url = base_url.rstrip("/") + "/"
        if urlparse(self.base_url).scheme not in ("http", "https"):
            raise ValueError("base_url doit utiliser HTTP ou HTTPS")
        self.timeout = timeout
        # Les transports injectés restent indépendants et gardent leur
        # signature (url, timeout) pour permettre des tests sans HTTP réel.
        transport = lire_octets
        if lire_octets is _telecharger_octets and api_key is not None:

            def transport_authentifie(url: str, limite: float) -> bytes:
                return _telecharger_octets(url, limite, api_key)

            transport = transport_authentifie
        self._lire = reessayer_http(
            tentatives=tentatives, pause_initiale=pause_initiale, dormir=dormir
        )(transport)

    def lire_json(self, chemin: str) -> object:
        """Télécharger un document JSON depuis une route relative au simulateur."""
        url = _url_sure(self.base_url, chemin)
        resultat: object = json.loads(self._lire(url, self.timeout))
        return resultat

    def iterer_pages(
        self,
        premiere_page: str,
        extraire: Callable[[object], tuple[list[dict[str, object]], str | None]],
    ) -> Iterator[dict[str, object]]:
        """Parcourir toutes les pages avec un extracteur adapté au vrai simulateur.

        L'extracteur indique les éléments et l'URL relative de la page suivante.
        Il doit être construit après lecture du fichier serveur_bornes.py.
        """
        page: str | None = premiere_page
        vues: set[str] = set()
        while page is not None:
            if page in vues:
                raise ValueError("boucle de pagination détectée")
            vues.add(page)
            actuelle = _url_sure(self.base_url, page)
            reponse = self.lire_json(actuelle)
            elements, prochaine = extraire(reponse)
            yield from elements
            page = urljoin(actuelle, prochaine) if prochaine is not None else None
