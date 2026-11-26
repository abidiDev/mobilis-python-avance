"""Moteur de facturation des trajets : règles R1 à R12 en Decimal.

Le moteur reçoit des objets du domaine déjà normalisés (jamais de chemin de
fichier). Le dédoublonnage R11 est assuré en amont par le lecteur de trajets :
un `trajet_id` n'arrive qu'une fois dans le flux.
"""

import bisect
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from zoneinfo import ZoneInfo

from mobilis.domain.anomalies import Anomalie, NiveauAnomalie, SignalerAnomalie
from mobilis.domain.models import (
    ConfigurationTarifaire,
    FormuleAbonnement,
    GrilleTarifaire,
    PeriodeAbonnement,
    Trajet,
)
from mobilis.services.tarification import Tarification, strategie_pour

PARIS = ZoneInfo("Europe/Paris")
DUREE_FANTOME = timedelta(minutes=2)
_ZERO = Decimal("0.00")
_SOURCE = "facturation"


def jour_local(instant: datetime) -> date:
    """Date civile Europe/Paris d'un instant (R1, R2, R6)."""
    return instant.astimezone(PARIS).date()


class StatutFacturation(StrEnum):
    """Issue de la facturation d'un trajet."""

    FACTURE = "facture"
    PENALITE = "penalite_non_restitution"  # R9
    FANTOME = "fantome"  # R8
    INCOHERENT = "horodatage_incoherent"  # R10


@dataclass(frozen=True, slots=True)
class LigneFacture:
    """Prix d'un trajet avant plafond journalier.

    `plafonnable` indique si le montant entre dans le cumul R6 de l'abonné.
    """

    trajet_id: str
    abonne_id: str | None
    formule: FormuleAbonnement
    jour: date
    statut: StatutFacturation
    montant: Decimal
    plafonnable: bool


@dataclass(frozen=True, slots=True)
class MontantDu:
    """Montant réellement dû : un trajet non plafonné ou une journée plafonnée."""

    jour: date
    formule: FormuleAbonnement
    brut: Decimal
    du: Decimal


class RegistreAbonnements:
    """Index en mémoire des périodes par abonné (≈5 000 abonnés : taille bornée)."""

    def __init__(self, periodes: Iterable[PeriodeAbonnement]) -> None:
        self._periodes: dict[str, list[PeriodeAbonnement]] = defaultdict(list)
        for periode in periodes:
            self._periodes[periode.id].append(periode)
        for historique in self._periodes.values():
            historique.sort(key=lambda p: p.debut)

    def connait(self, abonne_id: str) -> bool:
        return abonne_id in self._periodes

    def formule_active(self, abonne_id: str, jour: date) -> FormuleAbonnement | None:
        """R2 : période telle que debut ≤ jour ≤ fin (fin vide = en cours).

        Si plusieurs périodes se chevauchaient (aucun cas dans le kit), la plus
        récemment commencée l'emporte.
        """
        actives = [
            p
            for p in self._periodes.get(abonne_id, ())
            if p.debut <= jour and (p.fin is None or jour <= p.fin)
        ]
        return actives[-1].formule if actives else None


def grille_applicable(configuration: ConfigurationTarifaire, jour: date) -> GrilleTarifaire:
    """R1 : la dernière grille entrée en vigueur au plus tard ce jour-là."""
    dates = [g.en_vigueur_du for g in configuration.grilles]
    position = bisect.bisect_right(dates, jour)
    if position == 0:
        raise ValueError(f"aucune grille tarifaire en vigueur le {jour}")
    return configuration.grilles[position - 1]


class MoteurFacturation:
    """Applique R1–R12 à des trajets normalisés et dédoublonnés."""

    def __init__(
        self,
        configuration: ConfigurationTarifaire,
        abonnements: RegistreAbonnements,
        signaler: SignalerAnomalie,
        stations_connues: Collection[str] | None = None,
    ) -> None:
        self.configuration = configuration
        self.abonnements = abonnements
        self.signaler = signaler
        self.stations_connues = stations_connues
        self.compteurs: Counter[str] = Counter()
        self._seuil = timedelta(hours=configuration.seuil_non_restitution_heures)

    def strategie(self, formule: FormuleAbonnement, jour: date) -> Tarification:
        return strategie_pour(
            formule, grille_applicable(self.configuration, jour).formules[formule]
        )

    def _formule(self, trajet: Trajet, jour: date) -> FormuleAbonnement:
        """R2/R3 : formule active, sinon tarif occasionnel."""
        if trajet.abonne_id is None:
            self.compteurs["sans_abonne"] += 1
            return FormuleAbonnement.OCCASIONNEL
        if not self.abonnements.connait(trajet.abonne_id):
            self.compteurs["abonne_introuvable"] += 1
            self._signaler(
                trajet,
                "abonne_id",
                "ABONNE_INTROUVABLE",
                NiveauAnomalie.ALERTE,
                trajet.abonne_id,
                "Tarif occasionnel (R3) ; à transmettre au service client",
            )
            return FormuleAbonnement.OCCASIONNEL
        formule = self.abonnements.formule_active(trajet.abonne_id, jour)
        if formule is None:
            self.compteurs["abonnement_inactif"] += 1
            return FormuleAbonnement.OCCASIONNEL
        return formule

    def _signaler(
        self,
        trajet: Trajet,
        champ: str,
        code: str,
        niveau: NiveauAnomalie,
        valeur: str,
        decision: str,
    ) -> None:
        self.signaler(
            Anomalie(_SOURCE, None, trajet.trajet_id, champ, code, niveau, valeur, decision)
        )

    def _controler_stations(self, trajet: Trajet) -> None:
        """R12 : station hors référentiel → facturé normalement, mais signalé."""
        if self.stations_connues is None:
            return
        for champ, code in (
            ("station_depart", trajet.station_depart),
            ("station_arrivee", trajet.station_arrivee),
        ):
            if code is not None and code not in self.stations_connues:
                self.compteurs["station_inconnue"] += 1
                self._signaler(
                    trajet,
                    champ,
                    "STATION_INCONNUE",
                    NiveauAnomalie.ALERTE,
                    code,
                    "Facturé normalement (R12) et signalé",
                )

    def tarifer(self, trajet: Trajet) -> LigneFacture:
        """Prix d'un trajet, plafond journalier non encore appliqué."""
        jour = jour_local(trajet.debut)
        formule = self._formule(trajet, jour)
        self._controler_stations(trajet)

        def ligne(statut: StatutFacturation, montant: Decimal, plafonnable: bool) -> LigneFacture:
            self.compteurs[statut.value] += 1
            return LigneFacture(
                trajet.trajet_id, trajet.abonne_id, formule, jour, statut, montant, plafonnable
            )

        penalite = self.configuration.penalite_non_restitution
        if trajet.fin is None or trajet.station_arrivee is None:
            return ligne(StatutFacturation.PENALITE, penalite, False)  # R9
        duree = trajet.fin - trajet.debut  # instants avec fuseau : DST géré
        if duree < timedelta(0):  # R10
            self._signaler(
                trajet,
                "fin",
                "HORODATAGE_INCOHERENT",
                NiveauAnomalie.ERREUR,
                f"{trajet.debut.isoformat()} > {trajet.fin.isoformat()}",
                "Non facturé (R10) ; transmis à l'équipe technique",
            )
            return ligne(StatutFacturation.INCOHERENT, _ZERO, False)
        if duree > self._seuil:
            return ligne(StatutFacturation.PENALITE, penalite, False)  # R9
        if duree < DUREE_FANTOME and trajet.station_arrivee == trajet.station_depart:
            return ligne(StatutFacturation.FANTOME, _ZERO, False)  # R8
        strategie = self.strategie(formule, jour)
        prix = strategie.prix_trajet(duree, trajet.type_velo)
        return ligne(StatutFacturation.FACTURE, prix, strategie.plafonnee)

    def tarifer_tout(self, trajets: Iterable[Trajet]) -> Iterator[LigneFacture]:
        """Générateur : un trajet à la fois, quel que soit le volume."""
        for trajet in trajets:
            yield self.tarifer(trajet)

    def montants_dus(self, lignes: Iterable[LigneFacture]) -> Iterator[MontantDu]:
        """R6 : plafonne la somme des trajets d'un abonné par jour local.

        Les montants non plafonnables sont émis tout de suite. Les autres sont
        cumulés par (abonné, jour, formule) : la mémoire dépend du nombre
        d'abonnés-jours, pas du nombre de trajets.
        """
        cumuls: defaultdict[tuple[str, date, FormuleAbonnement], Decimal] = defaultdict(
            lambda: _ZERO
        )
        for lf in lignes:
            if lf.plafonnable and lf.abonne_id is not None:
                cumuls[(lf.abonne_id, lf.jour, lf.formule)] += lf.montant
            else:
                yield MontantDu(lf.jour, lf.formule, lf.montant, lf.montant)
        for (_, jour, formule), brut in cumuls.items():
            du = self.strategie(formule, jour).total_journee(brut)
            yield MontantDu(jour, formule, brut, du)
