"""Lecture en flux de l'historique des abonnements (abonnes.jsonl)."""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from mobilis.domain.anomalies import Anomalie, NiveauAnomalie, SignalerAnomalie
from mobilis.domain.models import FormuleAbonnement, PeriodeAbonnement

_CHAMPS = ("id", "formule", "debut", "fin", "commune")


class LecteurAbonnementsJsonl:
    """Implémentation de SourceAbonnements : une ligne JSON = une période.

    Toutes les périodes d'un même abonné sont conservées (R2). Une ligne
    illisible est signalée puis écartée sans interrompre la lecture.
    """

    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin

    def lire(self, signaler: SignalerAnomalie) -> Iterator[PeriodeAbonnement]:
        source = self.chemin.name
        with self.chemin.open(encoding="utf-8") as flux:
            for numero, texte in enumerate(flux, start=1):
                periode = _convertir(texte, numero, source, signaler)
                if periode is not None:
                    yield periode


def _convertir(
    texte: str, numero: int, source: str, signaler: SignalerAnomalie
) -> PeriodeAbonnement | None:
    def signaler_ici(
        identifiant: str, champ: str, code: str, niveau: NiveauAnomalie, valeur: str, decision: str
    ) -> None:
        signaler(Anomalie(source, numero, identifiant, champ, code, niveau, valeur, decision))

    try:
        objet: Any = json.loads(texte)
    except json.JSONDecodeError:
        signaler_ici(
            "",
            "ligne",
            "JSON_INVALIDE",
            NiveauAnomalie.ERREUR,
            texte.strip()[:80],
            "Écarter la ligne (export abîmé)",
        )
        return None
    if not isinstance(objet, dict) or any(champ not in objet for champ in _CHAMPS):
        signaler_ici(
            "",
            "ligne",
            "CHAMPS_MANQUANTS",
            NiveauAnomalie.ERREUR,
            texte.strip()[:80],
            "Écarter la ligne",
        )
        return None

    identifiant = str(objet["id"]).strip()
    brut_formule = str(objet["formule"])
    formule_normalisee = brut_formule.strip().lower()
    try:
        formule = FormuleAbonnement(formule_normalisee)
        debut = date.fromisoformat(str(objet["debut"]))
        fin = None if objet["fin"] is None else date.fromisoformat(str(objet["fin"]))
    except ValueError:
        signaler_ici(
            identifiant,
            "formule/debut/fin",
            "VALEUR_INVALIDE",
            NiveauAnomalie.ERREUR,
            texte.strip()[:80],
            "Écarter la ligne (valeur non interprétable)",
        )
        return None
    if brut_formule != formule_normalisee:
        signaler_ici(
            identifiant,
            "formule",
            "FORMULE_NON_NORMALISEE",
            NiveauAnomalie.INFO,
            brut_formule,
            f"Corrigée en « {formule.value} » (casse et espaces)",
        )
    if fin is not None and fin < debut:
        signaler_ici(
            identifiant,
            "fin",
            "PERIODE_INVERSEE",
            NiveauAnomalie.ERREUR,
            f"{debut} > {fin}",
            "Écarter la période",
        )
        return None
    return PeriodeAbonnement(identifiant, formule, debut, fin, str(objet["commune"]).strip())
