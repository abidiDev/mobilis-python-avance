"""Lecture des grilles tarifaires (tarifs.json) en valeurs Decimal exactes."""

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any

from mobilis.domain.anomalies import SignalerAnomalie
from mobilis.domain.models import (
    ConfigurationTarifaire,
    FormuleAbonnement,
    GrilleTarifaire,
    TarifFormule,
)


class TarifsInvalides(ValueError):
    """Le fichier de tarifs ne permet pas de facturer : on s'arrête net."""


def _montant(valeur: Any, champ: str) -> Decimal:
    # Les montants arrivent en texte ("1.20") : Decimal(str) évite toute perte float.
    if isinstance(valeur, float):
        raise TarifsInvalides(f"{champ} : montant en flottant interdit ({valeur!r})")
    try:
        montant = Decimal(str(valeur))
    except InvalidOperation as exc:
        raise TarifsInvalides(f"{champ} : montant illisible ({valeur!r})") from exc
    if not montant.is_finite():
        raise TarifsInvalides(f"{champ} : montant non fini ({valeur!r})")
    if montant < 0:
        raise TarifsInvalides(f"{champ} : montant négatif ({valeur!r})")
    return montant


def _tarif(brut: dict[str, Any], contexte: str) -> TarifFormule:
    try:
        plafond = brut["plafond_jour"]
        tarif = TarifFormule(
            minutes_incluses=int(brut["minutes_incluses"]),
            tranche_minutes=int(brut["tranche_minutes"]),
            prix_tranche=_montant(brut["prix_tranche"], f"{contexte}.prix_tranche"),
            supplement_electrique_tranche=_montant(
                brut["supplement_electrique_tranche"],
                f"{contexte}.supplement_electrique_tranche",
            ),
            frais_deblocage=_montant(brut["frais_deblocage"], f"{contexte}.frais_deblocage"),
            plafond_jour=None if plafond is None else _montant(plafond, f"{contexte}.plafond"),
        )
    except KeyError as exc:
        raise TarifsInvalides(f"{contexte} : champ manquant {exc}") from exc
    if tarif.tranche_minutes <= 0 or tarif.minutes_incluses < 0:
        raise TarifsInvalides(f"{contexte} : durées de tranche invalides")
    return tarif


class LecteurTarifsJson:
    """Implémentation de SourceTarifs.

    Contrairement aux exports de trajets, les tarifs sont une configuration :
    une valeur invalide lève `TarifsInvalides` plutôt que d'être signalée,
    car facturer avec une grille partielle produirait des montants faux.
    """

    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin

    def lire(self, signaler: SignalerAnomalie) -> ConfigurationTarifaire:
        try:
            brut = json.loads(self.chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TarifsInvalides(f"tarifs.json : JSON invalide ({exc})") from exc
        try:
            grilles = tuple(
                sorted(
                    (
                        GrilleTarifaire(
                            en_vigueur_du=date.fromisoformat(g["en_vigueur_du"]),
                            formules=MappingProxyType(
                                {
                                    FormuleAbonnement(nom): _tarif(t, f"{g['en_vigueur_du']}.{nom}")
                                    for nom, t in g["formules"].items()
                                }
                            ),
                        )
                        for g in brut["grilles"]
                    ),
                    key=lambda grille: grille.en_vigueur_du,
                )
            )
            configuration = ConfigurationTarifaire(
                devise=str(brut["devise"]),
                penalite_non_restitution=_montant(
                    brut["penalite_non_restitution"], "penalite_non_restitution"
                ),
                seuil_non_restitution_heures=int(brut["seuil_non_restitution_heures"]),
                grilles=grilles,
            )
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            if isinstance(exc, TarifsInvalides):
                raise
            raise TarifsInvalides(f"tarifs.json mal formé : {exc}") from exc
        if not grilles:
            raise TarifsInvalides("aucune grille tarifaire")
        for grille in grilles:
            manquantes = set(FormuleAbonnement) - set(grille.formules)
            if manquantes:
                raise TarifsInvalides(
                    f"grille du {grille.en_vigueur_du} : formules absentes {sorted(manquantes)}"
                )
        return configuration
