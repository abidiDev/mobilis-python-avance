"""Adaptateur au contrat réel du simulateur HTTP Mobilis (kit PYA-701).

Source officielle : outils/serveur_bornes.py (non modifié).
GET /stations?page=N -> {"page": int, "stations": [str], "page_suivante": int|null}
GET /stations/<code> -> code, velos_mecaniques, velos_electriques,
                        places_libres, horodatage ISO-8601.
Authentification : X-Api-Key.
"""

import time
from collections.abc import Callable
from datetime import datetime
from typing import cast
from urllib.parse import quote

from mobilis.adapters.bornes_http import ClientBornesHTTP, _telecharger_octets
from mobilis.services.etat_reseau import EtatBorne


def _objet_json(valeur: object) -> dict[str, object]:
    """Valider la racine JSON avant de consulter les champs."""
    if not isinstance(valeur, dict) or not all(isinstance(k, str) for k in valeur):
        raise ValueError("Réponse de l'API : objet JSON attendu")
    return cast(dict[str, object], valeur)


def _entier(champ: str, valeur: object) -> int:
    if type(valeur) is not int or valeur < 0:
        raise ValueError(f"Réponse de l'API : {champ} doit être un entier positif ou nul")
    return valeur


class ClientMobilisBornes:
    """Accès à toutes les bornes avec authentification et validation de schéma."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8765/",
        *,
        api_key: str = "demo-mobilis-2026",
        timeout: float = 5.0,
        tentatives: int = 3,
        pause_initiale: float = 0.1,
        lire_octets: Callable[[str, float], bytes] = _telecharger_octets,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("La clé X-Api-Key ne peut pas être vide")
        self.http = ClientBornesHTTP(
            base_url,
            timeout=timeout,
            tentatives=tentatives,
            pause_initiale=pause_initiale,
            lire_octets=lire_octets,
            dormir=dormir,
            api_key=api_key,
        )

    def lister_codes_stations(self) -> list[str]:
        """Parcourir les pages de 25 codes, et empêcher les boucles de pagination."""
        page = 1
        pages_vues: set[int] = set()
        codes: list[str] = []
        codes_vus: set[str] = set()
        while True:
            if page in pages_vues:
                raise ValueError("Boucle de pagination Mobilis détectée")
            pages_vues.add(page)
            document = _objet_json(self.http.lire_json(f"stations?page={page}"))
            numero = document.get("page")
            if type(numero) is not int or numero != page:
                raise ValueError(f"Pagination Mobilis : page incohérente ({numero!r})")
            lot = document.get("stations")
            if not isinstance(lot, list) or not all(
                isinstance(code, str) and code for code in lot
            ):
                raise ValueError("Pagination Mobilis : stations doit contenir des codes")
            for code in cast(list[str], lot):
                if code in codes_vus:
                    raise ValueError(f"Code station répété entre les pages : {code}")
                codes_vus.add(code)
                codes.append(code)
            suivante = document.get("page_suivante")
            if suivante is None:
                break
            if type(suivante) is not int or suivante < 1:
                raise ValueError("Pagination Mobilis : page_suivante invalide")
            page = suivante
        return codes

    def lire_etat(self, code: str) -> EtatBorne:
        """Lire une borne et calculer la somme réelle des deux types de vélos."""
        if not code or "/" in code or "?" in code or "#" in code:
            raise ValueError("Code station invalide pour la route HTTP")
        document = _objet_json(self.http.lire_json(f"stations/{quote(code, safe='')}"))
        if document.get("code") != code:
            raise ValueError(f"Réponse pour {code} : code station différent")
        meca = _entier("velos_mecaniques", document.get("velos_mecaniques"))
        elec = _entier("velos_electriques", document.get("velos_electriques"))
        libres = _entier("places_libres", document.get("places_libres"))
        brut = document.get("horodatage")
        if not isinstance(brut, str):
            raise ValueError(f"Réponse pour {code} : horodatage absent")
        try:
            horodatage = datetime.fromisoformat(brut)
        except ValueError as exc:
            raise ValueError(f"Réponse pour {code} : horodatage invalide") from exc
        if horodatage.tzinfo is None or horodatage.utcoffset() is None:
            raise ValueError(f"Réponse pour {code} : horodatage sans fuseau")
        return EtatBorne(
            code_station=code,
            velos_disponibles=meca + elec,
            places_libres=libres,
            velos_mecaniques=meca,
            velos_electriques=elec,
            horodatage=horodatage,
        )
