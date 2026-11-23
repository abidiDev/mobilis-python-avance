# Collaboration — Mobilis (binôme)

## Responsabilité par User Story

| Responsable | User Stories | Tâches |
|---|---|---|
| A — @abidiDev | Stations #1, API / État temps réel #4, Livraison #5 | #6, #7, #9, #10, #11, #17, #18, #19, #20, #21 |
| B — binôme, compte à ajouter | Trajets #2, Facturation #3 | #12, #13, #14, #15, #16 |

Chacun réalise toutes les tâches de ses US : code, tests et documentation. L’autre membre relit les PR. La tâche préalable #8 est un accord commun sur les interfaces, consigné par A. A coordonne la livraison ; chacun rédige son bilan individuel et participe à la démonstration. Les tickets B attendent le compte du binôme pour leur assignation GitHub.

## Stratégie GitHub Flow
- `main` est la seule branche permanente et doit rester stable.
- Une tâche de développement = une branche courte = une pull request. Une User Story peut regrouper plusieurs tâches et PR.
- Préfixes : `feature/`, `fix/`, `test/`, `docs/`, `chore/`.
- Exemple : `feature/9-station-model` (9 est le vrai numéro GitHub de l'issue).
- Après le commit initial du squelette et de la configuration, pas de commit direct sur `main` : PR obligatoire, approuvée par l’autre membre et CI verte.
- Fusion recommandée : **Squash and merge**, puis suppression de la branche.

## Travailler sur une tâche
```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/9-station-model
# développer, tester, committer
git add .
git commit -m "feat(stations): implement immutable station model"
git push -u origin feature/9-station-model
```
Ouvrir une PR vers `main`, inclure `Closes #9` pour la tâche (adapter au vrai numéro GitHub) et demander une revue au binôme. Utiliser `Refs #N` pour l’US parente. Ne fermer l’US que lorsque toutes ses tâches et ses critères sont validés.

## Avant chaque PR
Depuis la racine du dépôt, utiliser ces commandes PowerShell avec l’environnement Python 3.11 déjà créé. Le contrôle GitHub Actions correspondant s’appelle `lint-type-test`.
```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy --strict src/mobilis
.\.venv\Scripts\python.exe -m pytest -q
```

## Définition de terminé (DoD)
1. Critères d'acceptation satisfaits ; cas limites et erreurs documentés.
2. Tests pertinents au vert ; `ruff` et `mypy --strict` sans erreur.
3. Documentation et journal des anomalies mis à jour si pertinents.
4. PR liée à une issue, relue par le binôme et fusionnée dans `main`.
5. La fonctionnalité est démontrable, avec résultat reproductible.

## Rituel binôme
- Point de 10 minutes en début de séance : progrès, blocages, priorité.
- Une revue croisée sur chaque PR.
- Chacun assure les tests et la qualité de ses US ; l’autre vérifie les PR.
- Décisions importantes consignées dans `docs/decisions.md`.

## Données brutes
Ne pas versionner les données brutes du kit ; configurer leur chemin dans la future CLI. Ne jamais modifier les exports à la main. Le code de démarrage et les fichiers de configuration sont à versionner. Conserver les archives et données à côté du dépôt.
