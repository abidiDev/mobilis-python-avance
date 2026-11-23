# Configuration GitHub Projects — Mobilis

Les Issues sont créées : US #1–#5 et tâches #6–#21. La correspondance exacte figure dans BACKLOG.md. Le Project et la protection de main restent à configurer.

## Initialisation
1. Créer un dépôt **public** `abidiDev/mobilis-python-avance`. Le propriétaire ajoutera lui-même son binôme plus tard. Ne pas ajouter de README, de licence ou de .gitignore lors de la création : le dépôt local possède déjà ses fichiers.
2. Créer un **GitHub Project** de type Board : `Mobilis — Team Board`.
3. Lier le dépôt au Project et activer l'ajout automatique des issues pertinentes si possible.
4. Créer les statuts : **Backlog**, **Ready**, **In progress**, **In review**, **Done**.
5. Ajouter les champs : `Priority` (P0/P1/P2), `Size` (1/2/3/5), `Iteration` (sprint), `Module` (Setup/Stations/Trajets/Facturation/API/Livraison).
6. Créer les vues `Board` (par Status), `Sprint` (filtrée par Iteration), `Par membre` (groupée par Assignee), `Roadmap` si dates connues.
7. Avant d’utiliser les formulaires qui appliquent `user-story` et `tech-task`, créer les labels d'issues : `user-story`, `tech-task`, `bug`, `documentation`, `quality`, `blocked` ; éventuellement `module:*`.
8. Créer les 5 US de `BACKLOG.md` comme **Issues**, puis les tâches techniques. Utiliser les **sub-issues** quand disponibles, sinon relier les tickets par leurs descriptions.
9. Activer le passage des Issues fermées vers Done. Une PR ferme sa tâche avec `Closes #N` et référence l’US avec `Refs #N` ; fermer l’US seulement après validation de toutes ses tâches et de ses critères.
10. Après une première CI réussie sous Python 3.11, configurer la protection de `main` : PR obligatoire, revue par un pair, check `lint-type-test` requis (si le plan GitHub du dépôt permet ces règles).

## Politique d'équipe
- Aucun développement avant accord sur le contrat (types, signatures, formats de données).
- Une tâche = un responsable + un relecteur (l’autre personne). Une tâche de développement = une branche courte = une PR. Une US peut regrouper plusieurs tâches. Utiliser Squash and merge, puis supprimer la branche.
- Une seule tâche principale en cours par membre ; petites branches ; PR de taille raisonnable.
- Ne pas lancer le sprint suivant si le cas précédent n'a pas de résultat démontrable.
- Pas de modification manuelle des données brutes.

## Attention aux permissions du dépôt
GitHub peut limiter l'application de protections de branches pour les dépôts privés sur certains plans. Dans ce cas, garder exactement les mêmes règles **par convention d'équipe** et vérifier les checks des PR avant merge.

## Dépôt commun et nouvelle machine

Dépôt public : https://github.com/abidiDev/mobilis-python-avance

Sur une nouvelle machine, cloner le dépôt puis suivre le README pour créer un
environnement Python 3.11 local. Chaque membre récupère séparément les données
du kit officiel. Les archives et `.venv` restent en dehors de Git.

```powershell
git clone https://github.com/abidiDev/mobilis-python-avance.git
cd mobilis-python-avance
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
```

Dans **Actions**, le contrôle attendu est `lint-type-test` du workflow **Python CI**.
La protection de `main` doit être activée après son premier passage réussi.
Le propriétaire ajoutera son binôme au dépôt et au Project ultérieurement.

Références :
- [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)
- [Créer et configurer un Project](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/quickstart-for-projects)
- [CI Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)

## Réglages restant à effectuer

### Tableau

1. Ouvrir [Projects du dépôt](https://github.com/abidiDev/mobilis-python-avance/projects), puis **New project**.
2. Choisir **Board**, nommer le tableau **Mobilis — Team Board** et importer les Issues du dépôt si l’option est proposée.
3. Créer les statuts **Backlog**, **Ready**, **In progress**, **In review**, **Done**. Ajouter les 21 Issues existantes, sans en créer de doublons. Les liens des tâches sont dans chaque US.
4. Afficher **Assignees** et **Labels**. Ajouter **Priority** (P0/P1/P2), **Size** (1/2/3/5), **Iteration** et **Module**. Les valeurs de sprint, module et taille sont déjà renseignées dans les tickets ; fixer les dates d’itération une fois le calendrier convenu.
5. Ajouter les vues **Board**, **Sprint** et **Par membre**. Activer le passage des Issues fermées vers Done. Utiliser Ready seulement pour les tâches dont les dépendances sont satisfaites.
6. Les tâches A sont affectées à @abidiDev. Les tâches B attendent le compte du binôme ; celui-ci doit aussi recevoir l’accès au Project.

### Protection de main

Dans **Settings > Branches**, créer une règle de protection classique pour `main` (ou les règles équivalentes dans un ruleset actif) :

- Exiger une Pull Request et **1 approbation**.
- Exiger la réussite du contrôle **lint-type-test** et la résolution des discussions.
- Interdire les force-push et la suppression de main.
- Dans **Settings > General**, conserver **Squash merging** et activer la suppression automatique des branches fusionnées.

Le binôme doit être invité pour fournir l’approbation ; l’auteur ne peut pas approuver sa propre PR. La CI verte et les conventions écrites ne remplacent pas l’activation de ces réglages.

### Connexion Git sur le PC

La publication initiale a utilisé la connexion GitHub de l’application. Le `git push` local a signalé une authentification invalide. Avant la prochaine publication depuis VS Code, reconnecter le compte GitHub avec le gestionnaire d’identifiants Git ; ne pas placer de mot de passe ou de jeton dans les fichiers du projet.
