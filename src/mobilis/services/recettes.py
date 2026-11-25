"""Recettes mensuelles par formule et effet du changement tarifaire du 1er octobre 2026.

Mois et jours sont ceux de la date locale (Europe/Paris) de début du trajet,
comme pour le choix de la grille (R1) et le plafond journalier (R6).
"""

import dataclasses
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from mobilis.domain.models import ConfigurationTarifaire, FormuleAbonnement, Trajet
from mobilis.services.facturation import LigneFacture, MoteurFacturation, StatutFacturation

Cle = tuple[str, FormuleAbonnement]  # ("2026-08", formule)
_ZERO = Decimal("0.00")


def mois(jour: date) -> str:
    return f"{jour.year:04d}-{jour.month:02d}"


@dataclass(frozen=True, slots=True)
class RapportRecettes:
    """Agrégats de taille bornée : mois × formules, quel que soit le volume."""

    recettes: dict[Cle, Decimal]
    economies_plafond: dict[Cle, Decimal]
    trajets: dict[Cle, int]
    statuts: dict[StatutFacturation, int]

    def total_mois(self, valeur_mois: str) -> Decimal:
        return sum((v for (m, _), v in self.recettes.items() if m == valeur_mois), _ZERO)

    def total(self) -> Decimal:
        return sum(self.recettes.values(), _ZERO)


def analyser_recettes(moteur: MoteurFacturation, trajets: Iterable[Trajet]) -> RapportRecettes:
    """Facture le flux de trajets et agrège les montants dus par mois et formule.

    Pipeline : trajets → tarifer_tout → compter → montants_dus (plafond R6).
    """
    nb_trajets: Counter[Cle] = Counter()
    statuts: Counter[StatutFacturation] = Counter()

    def compter(lignes: Iterable[LigneFacture]) -> Iterator[LigneFacture]:
        for ligne in lignes:
            nb_trajets[(mois(ligne.jour), ligne.formule)] += 1
            statuts[ligne.statut] += 1
            yield ligne

    recettes: defaultdict[Cle, Decimal] = defaultdict(lambda: _ZERO)
    economies: defaultdict[Cle, Decimal] = defaultdict(lambda: _ZERO)
    for montant in moteur.montants_dus(compter(moteur.tarifer_tout(trajets))):
        cle = (mois(montant.jour), montant.formule)
        recettes[cle] += montant.du
        economies[cle] += montant.brut - montant.du
    return RapportRecettes(dict(recettes), dict(economies), dict(nb_trajets), dict(statuts))


def avec_grille_unique(configuration: ConfigurationTarifaire, du: date) -> ConfigurationTarifaire:
    """Configuration contrefactuelle : la grille entrée en vigueur à `du` s'applique partout.

    Sert à isoler l'effet prix : mêmes trajets, mêmes abonnés, seule la grille change.
    """
    grilles = tuple(g for g in configuration.grilles if g.en_vigueur_du == du)
    if not grilles:
        raise ValueError(f"aucune grille en vigueur au {du}")
    return dataclasses.replace(
        configuration, grilles=(dataclasses.replace(grilles[0], en_vigueur_du=date.min),)
    )


def effet_prix(reel: RapportRecettes, contrefactuel: RapportRecettes) -> dict[Cle, Decimal]:
    """Écart (réel − contrefactuel) par mois et formule : effet du seul changement de grille."""
    cles = reel.recettes.keys() | contrefactuel.recettes.keys()
    return {
        cle: reel.recettes.get(cle, _ZERO) - contrefactuel.recettes.get(cle, _ZERO)
        for cle in sorted(cles)
    }
