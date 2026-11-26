"""Tests T-10 : moteur de facturation R1–R12 et exemples E1–E6 de la direction."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType

import pytest

from mobilis.domain.anomalies import CollecteurAnomalies
from mobilis.domain.models import (
    ConfigurationTarifaire,
    FormuleAbonnement,
    GrilleTarifaire,
    PeriodeAbonnement,
    TarifFormule,
    Trajet,
    TypeVelo,
)
from mobilis.services.facturation import (
    MoteurFacturation,
    RegistreAbonnements,
    StatutFacturation,
    grille_applicable,
)

F = FormuleAbonnement
D = Decimal


def _grille(
    du: date, valeurs: dict[F, tuple[int, int, str, str, str, str | None]]
) -> GrilleTarifaire:
    return GrilleTarifaire(
        du,
        MappingProxyType(
            {
                f: TarifFormule(
                    v[0], v[1], D(v[2]), D(v[3]), D(v[4]), None if v[5] is None else D(v[5])
                )
                for f, v in valeurs.items()
            }
        ),
    )


# Valeurs recopiées de tarifs.json du kit (le kit n'est pas versionné).
CONFIG = ConfigurationTarifaire(
    devise="EUR",
    penalite_non_restitution=D("150.00"),
    seuil_non_restitution_heures=24,
    grilles=(
        _grille(
            date(2025, 1, 1),
            {
                F.ANNUEL: (30, 30, "1.00", "0.50", "0.00", "12.00"),
                F.MENSUEL: (30, 30, "1.00", "0.50", "0.00", "15.00"),
                F.SOLIDAIRE: (45, 30, "0.50", "0.25", "0.00", "5.00"),
                F.OCCASIONNEL: (0, 15, "0.60", "0.40", "1.00", None),
            },
        ),
        _grille(
            date(2026, 10, 1),
            {
                F.ANNUEL: (30, 30, "1.20", "0.60", "0.00", "14.00"),
                F.MENSUEL: (30, 30, "1.20", "0.60", "0.00", "18.00"),
                F.SOLIDAIRE: (45, 30, "0.50", "0.25", "0.00", "5.00"),
                F.OCCASIONNEL: (0, 15, "0.75", "0.50", "1.20", None),
            },
        ),
    ),
)

ABONNES = [
    PeriodeAbonnement("A-ANNUEL", F.ANNUEL, date(2024, 1, 1), None, "Valmont"),
    PeriodeAbonnement("A-MENSUEL", F.MENSUEL, date(2026, 9, 1), date(2026, 9, 30), "Valmont"),
]


def _trajet(
    abonne: str | None,
    debut: str,
    minutes: float | None = None,
    *,
    fin: str | None = None,
    velo: TypeVelo = TypeVelo.MECANIQUE,
    depart: str = "MB-0001",
    arrivee: str | None = "MB-0002",
    tid: str = "T1",
) -> Trajet:
    instant = datetime.fromisoformat(debut)
    if fin is not None:
        fin_instant: datetime | None = datetime.fromisoformat(fin)
    elif minutes is not None:
        fin_instant = instant + timedelta(minutes=minutes)
    else:
        fin_instant = None
    return Trajet(tid, abonne, "V1", velo, depart, instant, arrivee, fin_instant, None)


def _moteur(
    journal: CollecteurAnomalies | None = None, stations: set[str] | None = None
) -> MoteurFacturation:
    signaler = journal.signaler if journal else (lambda _: None)
    return MoteurFacturation(CONFIG, RegistreAbonnements(ABONNES), signaler, stations)


def _total(moteur: MoteurFacturation, trajets: list[Trajet]) -> Decimal:
    dus = moteur.montants_dus(moteur.tarifer_tout(trajets))
    return sum((m.du for m in dus), D("0"))


MECA, ELEC = TypeVelo.MECANIQUE, TypeVelo.ELECTRIQUE


@pytest.mark.parametrize(
    ("exemple", "trajets", "attendu"),
    [
        ("E1", [_trajet("A-ANNUEL", "2026-09-10T08:00:00+02:00", 25)], "0.00"),
        ("E2", [_trajet("A-ANNUEL", "2026-09-10T08:00:00+02:00", 25, velo=ELEC)], "0.50"),
        ("E3", [_trajet("A-MENSUEL", "2026-09-10T08:00:00+02:00", 61)], "2.00"),
        ("E4", [_trajet(None, "2026-10-05T08:00:00+02:00", 20, velo=ELEC)], "3.70"),
        (
            "E5",
            [
                _trajet("A-ANNUEL", f"2026-08-12T{h:02d}:00:00+02:00", 180, tid=f"T{h}")
                for h in (6, 10, 14)
            ],
            "12.00",
        ),
        (
            "E6",
            [
                _trajet(
                    "A-ANNUEL",
                    "2026-10-25T02:40:00+02:00",
                    fin="2026-10-25T02:10:00+01:00",
                )
            ],
            "0.00",
        ),
    ],
)
def test_exemples_valides_par_la_direction(
    exemple: str, trajets: list[Trajet], attendu: str
) -> None:
    assert _total(_moteur(), trajets) == D(attendu), exemple


def test_r1_grille_selon_date_locale_et_non_utc() -> None:
    # 30/09 22:30 UTC = 01/10 00:30 à Paris : nouvelle grille.
    assert grille_applicable(CONFIG, date(2026, 9, 30)).en_vigueur_du == date(2025, 1, 1)
    trajet = _trajet(None, "2026-09-30T22:30:00+00:00", 20, velo=ELEC)
    assert _moteur().tarifer(trajet).montant == D("3.70")


def test_r2_abonnement_expire_donne_tarif_occasionnel() -> None:
    # A-MENSUEL a pris fin le 30/09 (inclus) : le 01/10 il est occasionnel.
    moteur = _moteur()
    assert (
        moteur.tarifer(_trajet("A-MENSUEL", "2026-09-30T12:00:00+02:00", 10)).formule is F.MENSUEL
    )
    ligne = moteur.tarifer(_trajet("A-MENSUEL", "2026-10-01T12:00:00+02:00", 10))
    assert ligne.formule is F.OCCASIONNEL
    assert moteur.compteurs["abonnement_inactif"] == 1


def test_r3_abonne_introuvable_signale() -> None:
    journal = CollecteurAnomalies()
    ligne = _moteur(journal).tarifer(_trajet("A-FANTOME", "2026-09-10T08:00:00+02:00", 10))
    assert ligne.formule is F.OCCASIONNEL
    assert [a.code_anomalie for a in journal.elements] == ["ABONNE_INTROUVABLE"]


def test_r6_plafond_par_jour_local_et_pas_pour_occasionnel() -> None:
    moteur = _moteur()
    # Deux jours différents : pas de plafond commun (2 × 5,00 €).
    deux_jours = [
        _trajet("A-ANNUEL", "2026-08-12T23:00:00+02:00", 180, tid="T1"),
        _trajet("A-ANNUEL", "2026-08-13T10:00:00+02:00", 180, tid="T2"),
    ]
    assert _total(moteur, deux_jours) == D("10.00")
    # Occasionnel : 3 trajets de 3 h, jamais plafonnés.
    occasionnels = [
        _trajet(None, f"2026-08-12T{h:02d}:00:00+02:00", 180, tid=f"O{h}") for h in (6, 10, 14)
    ]
    assert _total(moteur, occasionnels) == 3 * (D("1.00") + 12 * D("0.60"))


def test_r8_trajet_fantome_non_facture() -> None:
    trajet = _trajet("A-ANNUEL", "2026-08-12T08:00:00+02:00", 1.5, arrivee="MB-0001", velo=ELEC)
    ligne = _moteur().tarifer(trajet)
    assert (ligne.statut, ligne.montant) == (StatutFacturation.FANTOME, D("0.00"))


@pytest.mark.parametrize(
    "trajet",
    [
        _trajet("A-ANNUEL", "2026-08-12T08:00:00+02:00", None, arrivee=None),
        _trajet("A-ANNUEL", "2026-08-12T08:00:00+02:00", 24 * 60 + 1),
    ],
    ids=["sans_retour", "plus_de_24h"],
)
def test_r9_penalite_hors_plafond(trajet: Trajet) -> None:
    moteur = _moteur()
    ligne = moteur.tarifer(trajet)
    assert (ligne.statut, ligne.montant, ligne.plafonnable) == (
        StatutFacturation.PENALITE,
        D("150.00"),
        False,
    )
    assert _total(moteur, [trajet]) == D("150.00")


def test_trajet_horodatage_incoherent_non_facture() -> None:
    """R10 — appliquée aux 145 durées négatives du kit (voir decisions.md)."""
    journal = CollecteurAnomalies()
    trajet = _trajet("A-ANNUEL", "2026-08-01T09:23:43+02:00", fin="2026-08-01T08:24:43+02:00")
    ligne = _moteur(journal).tarifer(trajet)
    assert (ligne.statut, ligne.montant) == (StatutFacturation.INCOHERENT, D("0.00"))
    assert journal.elements[0].code_anomalie == "HORODATAGE_INCOHERENT"


def test_r12_station_inconnue_facturee_et_signalee() -> None:
    journal = CollecteurAnomalies()
    trajet = _trajet(None, "2026-08-12T08:00:00+02:00", 20, arrivee="MB-9999")
    ligne = _moteur(journal, stations={"MB-0001", "MB-0002"}).tarifer(trajet)
    assert ligne.statut is StatutFacturation.FACTURE
    assert ligne.montant == D("2.20")
    assert [(a.code_anomalie, a.valeur_observee) for a in journal.elements] == [
        ("STATION_INCONNUE", "MB-9999")
    ]
