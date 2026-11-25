# Décisions du projet

| Date | Décision | Motif |
|---|---|---|
| 2026-11-23 | Conserver le squelette officiel `src/` et `pyproject.toml` | Partir de la base fournie par le professeur |
| 2026-11-23 | Utiliser Python 3.11 en local et dans la CI | Version minimale officielle, déjà installée sur le PC |
| 2026-11-23 | Conserver les données en dehors du dépôt | Respecter la consigne du kit et préserver les exports |
| 2026-11-23 | GitHub Flow, revue croisée et contrôle `lint-type-test` | Garder `main` vérifiable et rendre les contributions lisibles |
| 2026-11-23 | Responsabilité par US : A Stations/API/Livraison ; B Trajets/Facturation | Chacun développe ses US de bout en bout, tests et documentation inclus ; revue croisée conservée |
| 2026-11-23 | Développement parallèle après accord #8 ; intégration finale commune | Éviter une attente artificielle entre API et facturation, tout en validant les échanges réels |

À compléter après exploration : modèles et signatures, gestion des anomalies,
stratégie de dédoublonnage, temps et fuseaux, choix de concurrence.

## 2026-11-23 — Noyau commun T-03 sur branche dédiée

Le package `src/mobilis/domain/` définit les objets immuables `Station`, `Trajet`,
`PeriodeAbonnement`, `TarifFormule`, `GrilleTarifaire` et
`ConfigurationTarifaire`. Les statuts de station, types de vélo et formules
d'abonnement sont des `StrEnum`. Le package `domain/anomalies.py` partage
`Anomalie`, `NiveauAnomalie`, `SignalerAnomalie` et un collecteur explicite.

Les adaptateurs s'engagent sur les ports de lecture de `domain/contracts.py`
(`SourceStations`, `SourceTrajets`, `SourceAbonnements`, `SourceTarifs`).
Un port de lecture fournit des objets normalisés et non un rapport métier.
Le service reçoit les objets normalisés ; la CLI assemble les deux.

**Décisions non validées :** stratégie finale des doublons, ambiguïté des dates
locales au passage à l'heure d'hiver, fin d'abonnement inclusive/exclusive,
traitement des trajets sans restitution et codes d'erreur HTTP.
Les signatures HTTP/facturation spécifiques ne sont pas figées avant lecture de
`serveur_bornes.py` et `specification_facturation.md`.

Voir [contrats_t03.md](contrats_t03.md) pour les définitions précises
et les tâches de validation du binôme. **PR de centralisation proposée,
validation du binôme attendue.**

## 2026-11-25 — US-03 Facturation : décisions d'interprétation (proposées par B, à valider par A)

La spécification `specification_facturation.md` est appliquée telle quelle ;
les points qu'elle ne tranche pas sont décidés ici et couverts par un test.

| Question | Décision | Test |
|---|---|---|
| Ordre des règles | R9 (pas de retour) → R10 (fin < début) → R9 (> 24 h) → R8 (fantôme) → R4–R7 | `test_r9_*`, `test_trajet_horodatage_incoherent_non_facture`, `test_r8_*` |
| « Plus de 24 h » | Strictement supérieur au seuil | `test_r9_penalite_hors_plafond[plus_de_24h]` |
| « Moins de 2 minutes » | Strictement inférieur | `test_r8_trajet_fantome_non_facture` |
| Formule d'un trajet pénalisé | Celle de R2/R3 ; la pénalité n'entre jamais dans le plafond | `test_r9_penalite_hors_plafond` |
| Plafond R6 | Par (abonné, jour local de début, formule) ; seules les formules d'abonnement | `test_exemples_valides_par_la_direction[E5]`, `test_r6_*` |
| Périodes qui se chevauchent | La plus récemment commencée l'emporte (0 cas dans le kit) | — |
| Abonnement inactif | Tarif occasionnel, compté mais non signalé (R3 ne signale que les introuvables) | `test_r2_abonnement_expire_donne_tarif_occasionnel` |
| Formule mal écrite (`" ANNUEL"`) | Corrigée et signalée en `info` | `test_abonnes_lignes_abimees_signalees_et_historique_conserve` |
| Tarifs invalides | Exception `TarifsInvalides` : on ne facture pas avec une grille partielle | `test_tarifs_invalides_refuses` |
| Mois des recettes | Mois de la date locale de début du trajet | `test_recettes_par_mois_et_formule` |
| Effet du 1er octobre | Mêmes trajets refacturés avec l'ancienne grille sur toute la période | `test_effet_prix_isole_le_changement_de_grille` |

Contrat de tarification : classe abstraite `Tarification` (patron Stratégie) et deux
implémentations, `TarificationAbonnement` (plafond R6) et `TarificationOccasionnelle`.
Une ABC plutôt qu'un `Protocol` : le calcul R4/R5/R7 est commun et vit dans la classe
de base ; seules les règles de plafond diffèrent.

Mémoire : le moteur traite un trajet à la fois. Le cumul du plafond est indexé par
abonné-jour (au plus ~5 200 abonnés × 92 jours), donc borné quel que soit le nombre de trajets.

Résultats chiffrés : [resultats_us03.md](resultats_us03.md).
