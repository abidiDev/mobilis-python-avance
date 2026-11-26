"""Contrat de tarification et ses deux stratégies (R4, R5, R6, R7).

`Tarification` est une classe abstraite (patron Stratégie) : le moteur de
facturation choisit une implémentation selon la formule (R2/R3) et ne connaît
ensuite que ce contrat.

- `TarificationAbonnement` : prix R4 + R5, total journalier plafonné (R6).
- `TarificationOccasionnelle` : même calcul de prix, **sans** plafond (R6).
"""

from abc import ABC, abstractmethod
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from mobilis.domain.models import FormuleAbonnement, TarifFormule, TypeVelo

CENTIME = Decimal("0.01")


def arrondir(montant: Decimal) -> Decimal:
    """R7 : arrondi au centime le plus proche, la moitié vers le haut."""
    return montant.quantize(CENTIME, rounding=ROUND_HALF_UP)


def tranches_entamees(duree: timedelta, tranche_minutes: int) -> int:
    """Nombre de tranches commencées : une seconde suffit pour en entamer une."""
    if duree <= timedelta(0):
        return 0
    completes, reste = divmod(duree, timedelta(minutes=tranche_minutes))
    return completes + (1 if reste else 0)


class Tarification(ABC):
    """Contrat : prix d'un trajet, puis total d'une journée d'un même client."""

    def __init__(self, tarif: TarifFormule) -> None:
        self.tarif = tarif

    def prix_trajet(self, duree: timedelta, type_velo: TypeVelo) -> Decimal:
        """R4 (usage au-delà des minutes incluses) + R5 (supplément électrique)."""
        t = self.tarif
        usage = max(timedelta(0), duree - timedelta(minutes=t.minutes_incluses))
        prix = t.frais_deblocage + tranches_entamees(usage, t.tranche_minutes) * t.prix_tranche
        if type_velo is TypeVelo.ELECTRIQUE:
            prix += tranches_entamees(duree, t.tranche_minutes) * t.supplement_electrique_tranche
        return arrondir(prix)

    @property
    @abstractmethod
    def plafonnee(self) -> bool:
        """Vrai si les trajets d'une même journée partagent un plafond (R6)."""

    @abstractmethod
    def total_journee(self, total_brut: Decimal) -> Decimal:
        """Montant dû pour la somme des prix d'un client sur une journée locale."""


class TarificationAbonnement(Tarification):
    """Formules annuel, mensuel, solidaire : plafond journalier R6."""

    @property
    def plafonnee(self) -> bool:
        return self.tarif.plafond_jour is not None

    def total_journee(self, total_brut: Decimal) -> Decimal:
        plafond = self.tarif.plafond_jour
        return total_brut if plafond is None else min(total_brut, plafond)


class TarificationOccasionnelle(Tarification):
    """Formule occasionnelle : aucun plafond (R6), chaque trajet est dû en entier."""

    @property
    def plafonnee(self) -> bool:
        return False

    def total_journee(self, total_brut: Decimal) -> Decimal:
        return total_brut


def strategie_pour(formule: FormuleAbonnement, tarif: TarifFormule) -> Tarification:
    """Fabrique : la formule occasionnelle n'est jamais plafonnée."""
    if formule is FormuleAbonnement.OCCASIONNEL:
        return TarificationOccasionnelle(tarif)
    return TarificationAbonnement(tarif)
