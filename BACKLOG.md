# Mobilis — Product Backlog

Les 5 User Stories et les 16 tâches sont créées sur GitHub. Le tableau Project reste à configurer. Les critères pédagogiques hérités du starter sont à recouper avec le sujet officiel avant chaque cas. A désigne @abidiDev ; B désigne le binôme dont le compte sera ajouté ultérieurement.

Les IDs `US-XX` et `T-XX` ci-dessous sont des repères internes. Utiliser les vrais numéros GitHub Issues pour les branches et les références `Closes #N`.

## Responsabilité par User Story

| Responsable | User Stories | Tâches |
|---|---|---|
| A — @abidiDev | Trajets #2, API / État temps réel #4 | #6, #7, #8, #12, #13, #17, #18 |
| B — @plasticbagdancing | Stations #1, Facturation #3, Livraison #5 | #9, #10, #11, #14, #15, #16, #19, #20, #21 |

Chacun réalise toutes les tâches de ses US : code, tests et documentation. L’autre membre relit les PR. La tâche préalable #8 est un accord commun sur les interfaces, consigné par A. A coordonne la livraison ; chacun rédige son bilan individuel et participe à la démonstration. Les tickets B attendent le compte du binôme pour leur assignation GitHub.

## User Stories

### US-01 — Stations (Sprint 1, P0)
**En tant qu'analyste Mobilis, je veux charger et valider le référentiel des stations afin d'identifier les stations exploitables et les anomalies.**

Critères : dataclass `Station` immuable ; `Enum` de statut ; import CSV tel quel ; journal d'anomalies exhaustif sans arrêt à la première erreur ; tests pour encodage, valeurs invalides et cas limites ; résultat CLI reproductible.

### US-02 — Trajets (Sprint 2, P0)
**En tant qu'analyste, je veux analyser les trajets en flux afin de connaître les pics de fréquentation sans saturer la mémoire.**

Critères : lecture `.csv.gz` via générateurs ; trois formats de date ; dédoublonnage documenté ; agrégations matin/soir, semaine/week-end ; mémoire mesurée (`tracemalloc`) et méthode scalable ; tests.

### US-03 — Facturation (Sprint 3, P0)
**En tant que responsable financier, je veux calculer les recettes mensuelles et comparer les tarifs avant/après le 1er octobre 2026 afin d'expliquer les revenus.**

Critères : toutes règles R1-R12 appliquées ; `Decimal` uniquement ; contrat de tarification ABC ou Protocol, deux implémentations ; E1-E6 en tests paramétrés ; recettes par mois et formule ; résultat reproductible.

### US-04 — État temps réel (Sprint 4, P0)
**En tant qu'exploitant, je veux obtenir un état fiable de toutes les stations afin d'identifier celles qui sont vides/pleines et les écarts avec le référentiel.**

Critères : API simulée ; retries 503/504/429 avec Retry-After ; 8 requêtes simultanées max ; temps total <15 s dans les conditions du sujet ; comparatif séquentiel/threads/asyncio ; tests mockés sans serveur.

### US-05 — Livraison (Sprint 5, P0)
**En tant que développeur ou analyste, je veux installer et utiliser le paquet Mobilis en une commande afin de reproduire les analyses de façon fiable.**

Critères : package `src` / `pyproject.toml` ; `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"` ; commande `mobilis` avec `stations`, `frequentation`, `facturation`, `etat` ; >=15 tests ; ruff et `mypy --strict` verts ; GitHub Actions ; README ; dossier technique 12-20 pages ; démonstration.

## Tâches — Répartition validée

| ID | Lot | Responsable | Tâche | Dépend de | Taille |
|---|---|---|---|---|---|
| T-01 | 0 | A | Créer dépôt, importer squelette `demarrage/`, `.gitignore`, pyproject | — | 2 |
| T-02 | 0 | A | Configurer CI, templates Issues/PR, Project GitHub | T-01 | 2 |
| T-03 | 0 | A | Explorer kit, définir types et contrats, ouvrir journal anomalies | T-01 | 3 |
| T-04 | 1 | A | Dataclass Station, Enum, validations métier + tests | T-03 | 3 |
| T-05 | 1 | A | Lecture CSV, collecte anomalies et tests | T-03,T-04 (interface) | 5 |
| T-06 | 1 | A | Intégration stations, CLI provisoire, documentation & recette | T-04,T-05 | 2 |
| T-07 | 2 | B | Pipeline de générateurs, dates, dédoublonnage + tests | T-03 (contrats) ; T-06 pour intégration | 5 |
| T-08 | 2 | B | Fréquentation, agrégations, mesure mémoire + tests | T-07 (interface) | 5 |
| T-09 | 3 | B | Lecture tarifs / abonnés et contrat de tarification | T-03, T-07 (interface) | 5 |
| T-10 | 3 | B | Moteur de facturation Decimal, R1-R12, tests E1-E6 | T-09 (interface) | 5 |
| T-11 | 3 | B | Agrégation revenus mensuels et comparaison avant/après + tests | T-10 | 3 |
| T-12 | 4 | A | Client HTTP, décorateur retry/backoff et mocks | T-03 (contrat API) | 5 |
| T-13 | 4 | A | Concurrence <=8, benchmark 3 stratégies, état comparé | T-12 (interface), T-06 pour comparaison | 5 |
| T-14 | 5 | A | CLI finale des 4 commandes, erreurs et chemins configurables | T-03 ; T-06,T-08,T-11,T-13 pour intégration finale | 3 |
| T-15 | 5 | A | Installation sur machine vierge, README, métriques de qualité | T-14 | 3 |
| T-16 | 5 | A | Dossier technique, bilans individuels, présentation et répétition | T-15 | 5 |

Taille indicative en points, non en heures. La personne non responsable devient relecteur. T-03 fixe les contrats à deux ; le responsable de l’US réalise ensuite ses tâches de bout en bout. Pour T-16, A coordonne le dossier et chaque membre produit sa contribution individuelle. Une PR ferme sa tâche (`Closes #N`) et référence son US (`Refs #N`) ; l’US ne ferme qu’après validation de tous ses critères.

T-01 (#6) est terminée et fermée. T-02 (#7) reste ouverte : CI et templates sont en place ; Project, protection de main et revue restent à finaliser.

## Avancer en parallèle

Les anciens numéros de sprint conservés dans les tickets désignent les lots du starter, sans imposer un calendrier successif.

1. Ensemble : valider #8 (codes de station, modèle de trajet, dates et durées, anomalies, signatures utilisées par la CLI).
2. A développe Stations puis API ; B développe Trajets puis Facturation. Chacun utilise au besoin de petits jeux de test et des réponses simulées conformes aux contrats.
3. A peut préparer les commandes et la documentation en parallèle. La validation finale de Livraison exige l’intégration des résultats des deux membres.

Les dépendances du tableau indiquent les interfaces nécessaires et les validations finales. L’API ne dépend pas de la facturation. Les critères pédagogiques restent à vérifier dans le sujet officiel ; cette organisation ne constitue pas une consigne d’ordre imposée par l’enseignant. Fixer les dates à partir de l’échéance réelle.

## Correspondance avec les tickets GitHub

| Repère | Issue | Sujet |
|---|---|---|
| US-01 | [#1](https://github.com/abidiDev/mobilis-python-avance/issues/1) | Stations |
| US-02 | [#2](https://github.com/abidiDev/mobilis-python-avance/issues/2) | Trajets |
| US-03 | [#3](https://github.com/abidiDev/mobilis-python-avance/issues/3) | Facturation |
| US-04 | [#4](https://github.com/abidiDev/mobilis-python-avance/issues/4) | État temps réel |
| US-05 | [#5](https://github.com/abidiDev/mobilis-python-avance/issues/5) | Livraison |
| T-01 | [#6](https://github.com/abidiDev/mobilis-python-avance/issues/6) | Créer dépôt, importer squelette `demarrage/`, `.gitignore`, pyproject |
| T-02 | [#7](https://github.com/abidiDev/mobilis-python-avance/issues/7) | Configurer CI, templates Issues/PR, Project GitHub |
| T-03 | [#8](https://github.com/abidiDev/mobilis-python-avance/issues/8) | Explorer kit, définir types et contrats, ouvrir journal anomalies |
| T-04 | [#9](https://github.com/abidiDev/mobilis-python-avance/issues/9) | Dataclass Station, Enum, validations métier + tests |
| T-05 | [#10](https://github.com/abidiDev/mobilis-python-avance/issues/10) | Lecture CSV, collecte anomalies et tests |
| T-06 | [#11](https://github.com/abidiDev/mobilis-python-avance/issues/11) | Intégration stations, CLI provisoire, documentation & recette |
| T-07 | [#12](https://github.com/abidiDev/mobilis-python-avance/issues/12) | Pipeline de générateurs, dates, dédoublonnage + tests |
| T-08 | [#13](https://github.com/abidiDev/mobilis-python-avance/issues/13) | Fréquentation, agrégations, mesure mémoire + tests |
| T-09 | [#14](https://github.com/abidiDev/mobilis-python-avance/issues/14) | Lecture tarifs / abonnés et contrat de tarification |
| T-10 | [#15](https://github.com/abidiDev/mobilis-python-avance/issues/15) | Moteur de facturation Decimal, R1-R12, tests E1-E6 |
| T-11 | [#16](https://github.com/abidiDev/mobilis-python-avance/issues/16) | Agrégation revenus mensuels et comparaison avant/après + tests |
| T-12 | [#17](https://github.com/abidiDev/mobilis-python-avance/issues/17) | Client HTTP, décorateur retry/backoff et mocks |
| T-13 | [#18](https://github.com/abidiDev/mobilis-python-avance/issues/18) | Concurrence <=8, benchmark 3 stratégies, état comparé |
| T-14 | [#19](https://github.com/abidiDev/mobilis-python-avance/issues/19) | CLI finale des 4 commandes, erreurs et chemins configurables |
| T-15 | [#20](https://github.com/abidiDev/mobilis-python-avance/issues/20) | Installation sur machine vierge, README, métriques de qualité |
| T-16 | [#21](https://github.com/abidiDev/mobilis-python-avance/issues/21) | Dossier technique, bilans individuels, présentation et répétition |

A correspond à @abidiDev. Les tâches B restent sans assignation jusqu’à l’invitation du binôme. Les tâches sont liées dans le corps des US ; la hiérarchie native de sub-issues peut être ajoutée ensuite.
