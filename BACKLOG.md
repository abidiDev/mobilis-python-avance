# Mobilis — Product Backlog (proposition initiale)

Les Issues et le Project ne sont pas encore créés sur GitHub. Les critères pédagogiques hérités du starter sont à recouper avec le sujet officiel avant chaque cas. A et B désignent les deux membres, à remplacer par leurs pseudos GitHub.

Les IDs `US-XX` et `T-XX` ci-dessous sont des repères internes. Après création, utiliser les vrais numéros GitHub Issues pour les branches et les références `Closes #N`.

## User Stories (créer chacune comme issue parent)

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

## Technical Issues — Répartition proposée

| ID | Sprint | Responsable | Tâche | Dépend de | Taille |
|---|---|---|---|---|---|
| T-01 | 0 | A | Créer dépôt, importer squelette `demarrage/`, `.gitignore`, pyproject | — | 2 |
| T-02 | 0 | B | Configurer CI, templates Issues/PR, Project GitHub | T-01 | 2 |
| T-03 | 0 | A | Explorer kit, définir types et contrats, ouvrir journal anomalies | T-01 | 3 |
| T-04 | 1 | A | Dataclass Station, Enum, validations métier + tests | T-03 | 3 |
| T-05 | 1 | B | Lecture CSV, collecte anomalies et tests | T-03,T-04 (interface) | 5 |
| T-06 | 1 | B | Intégration stations, CLI provisoire, documentation & recette | T-04,T-05 | 2 |
| T-07 | 2 | B | Pipeline de générateurs, dates, dédoublonnage + tests | T-06 | 5 |
| T-08 | 2 | A | Fréquentation, agrégations, mesure mémoire + tests | T-07 (interface) | 5 |
| T-09 | 3 | A | Lecture tarifs / abonnés et contrat de tarification | T-08 | 5 |
| T-10 | 3 | B | Moteur de facturation Decimal, R1-R12, tests E1-E6 | T-09 (interface) | 5 |
| T-11 | 3 | A | Agrégation revenus mensuels et comparaison avant/après + tests | T-10 | 3 |
| T-12 | 4 | B | Client HTTP, décorateur retry/backoff et mocks | T-11 | 5 |
| T-13 | 4 | A | Concurrence <=8, benchmark 3 stratégies, état comparé | T-12 (interface) | 5 |
| T-14 | 5 | B | CLI finale des 4 commandes, erreurs et chemins configurables | T-13 | 3 |
| T-15 | 5 | A | Installation sur machine vierge, README, métriques de qualité | T-14 | 3 |
| T-16 | 5 | A | Dossier technique, bilans individuels, présentation et répétition | T-15 | 5 |

Taille indicative en points, non en heures. La personne non responsable devient relecteur. T-03, T-06 et T-16 se travaillent conjointement, avec le responsable unique indiqué. Découper au besoin en sous-tâches avec livrables et commits attribuables. Une PR ferme sa tâche (`Closes #N`) et référence son US (`Refs #N`) ; l’US ne ferme qu’après validation de tous ses critères.

Les fichiers locaux ne prouvent pas que T-01 et T-02 sont terminées : vérifier le dépôt distant, le Project et une exécution réelle de GitHub Actions avant de les fermer.

## Cadence
- **Sprint 0** : setup, contrats et outils GitHub.
- **Sprint 1** : cas 1 Stations de bout en bout.
- **Sprint 2** : cas 2 Trajets de bout en bout.
- **Sprint 3** : cas 3 Facturation de bout en bout.
- **Sprint 4** : cas 4 API temps réel de bout en bout.
- **Sprint 5** : cas 5 Livraison, documentation et soutenance.

La durée des sprints doit être définie d'après la date limite réelle de rendu.
