# Configuration GitHub Projects — Mobilis

Les 5 User Stories (#1–#5) et les 16 tâches (#6–#21) existent. Ne pas créer de doublons. Le tableau Project et la protection de main restent à configurer.

## Répartition par US

- @abidiDev (A) : Stations #1, API / État temps réel #4, Livraison #5, avec toutes leurs tâches.
- Binôme (B) : Trajets #2 et Facturation #3, avec toutes leurs tâches.
- #8 : accord initial commun sur les types, formats et signatures, consigné par A.
- Chaque responsable réalise code, tests et documentation ; l’autre relit les PR.
- A coordonne la livraison ; chaque membre prépare son bilan individuel et participe à la démonstration.
- Les tickets B restent sans assignation GitHub jusqu’à l’invitation du binôme. Le propriétaire lui donnera accès au dépôt et au Project.

## Créer le tableau

1. Ouvrir [Projects du dépôt](https://github.com/abidiDev/mobilis-python-avance/projects), puis **New project**.
2. Choisir une vue **Board** et nommer le tableau **Mobilis — Team Board**. Lier le dépôt au Project si nécessaire.
3. Ajouter les 21 Issues existantes du dépôt (option d’ajout depuis un dépôt). Les tâches sont reliées aux US dans leurs descriptions ; la hiérarchie native de sub-issues n’est pas encore configurée.
4. Utiliser **Status** comme champ des colonnes, avec **Backlog**, **Ready**, **In progress**, **In review**, **Done**.
5. Afficher **Assignees** et **Labels** sur les cartes.
6. Créer une vue **US** filtrée avec `label:user-story` et une vue **Tâches** filtrée avec `label:tech-task`. Ce sont deux vues du même Project.
7. Facultativement, ajouter Priority, Size, Module et Iteration. Les valeurs présentes dans les descriptions ne remplissent pas automatiquement les champs du Project. Les anciens numéros de sprint sont des repères de lots ; convenir des dates réelles à deux.
8. Activer le workflow qui passe les issues fermées à Done. Vérifier son fonctionnement sur #6, déjà terminée.

## Déplacer une carte au quotidien

Dans la vue **Tâches**, maintenir le clic sur une carte, la faire glisser vers la colonne souhaitée, puis relâcher. Le déplacement change son champ **Status**. On peut aussi modifier ce champ directement dans le Project.

| Colonne | Quand l’utiliser |
|---|---|
| Backlog | Travail prévu, encore à préparer |
| Ready | Objectif clair et interfaces nécessaires convenues |
| In progress | Son responsable commence à travailler dessus |
| In review | PR prête pour la relecture de l’autre membre |
| Done | Critères validés, CI verte, PR relue et fusionnée |

Exemple : A démarre #9 (modèle Station) : déplacer #9 de Ready vers In progress. Lors de l’ouverture de sa PR prête à relire, passer #9 à In review. Après revue et fusion, fermer la tâche avec `Closes #9` dans la PR ; vérifier son passage à Done.

Dans la vue **US**, passer Stations #1 à In progress dès que sa première tâche démarre. Laisser #1 en cours pendant que #9, #10 et #11 avancent séparément. Fermer #1 et la passer à Done seulement lorsque ses trois tâches et tous ses critères d’acceptation sont validés.

**Assignees** indique qui réalise le travail. **Status** indique son avancement. Déplacer une US ne déplace pas automatiquement ses tâches et ne change pas leurs responsables. Dans notre organisation, mettre une carte à Done ne suffit pas à valider son travail ; la fermeture de l’issue et les critères doivent également être vérifiés.

## Travail en parallèle et branches

Valider les contrats de #8, puis A avance sur Stations et API tandis que B avance sur Trajets et Facturation. Des jeux de test et des réponses simulées permettent de développer avant l’intégration finale. La livraison des quatre commandes exige les résultats des deux membres.

Une tâche de développement = une branche courte = une PR vers main. Une US peut donc contenir plusieurs PR, toutes réalisées par son responsable. La PR ferme sa tâche avec `Closes #N` et référence l’US avec `Refs #N`. Suivre [CONTRIBUTING.md](CONTRIBUTING.md), garder une tâche principale en cours par membre et faire une revue croisée.

## Protection de main

Dans **Settings > Branches**, créer une règle pour main, ou configurer les règles équivalentes dans un ruleset actif :

- Exiger une Pull Request et **1 approbation**.
- Exiger le contrôle **lint-type-test** et la résolution des discussions.
- Interdire les force-push et la suppression de main.
- Conserver **Squash merging** et activer la suppression automatique des branches fusionnées.

Le contrôle GitHub Actions a déjà réussi. Les règles ci-dessus restent à activer. L’auteur ne peut pas approuver sa propre PR : le binôme devra être invité pour fournir sa revue.

## Nouvelle machine et connexion Git

Cloner [le dépôt public](https://github.com/abidiDev/mobilis-python-avance), puis suivre le [README](README.md) pour créer l’environnement Python 3.11. Chaque membre récupère séparément le kit officiel ; les données brutes et l’environnement local ne sont pas versionnés.

La publication initiale a utilisé la connexion GitHub de l’application. Le git push local avait signalé une authentification invalide : reconnecter le compte GitHub avec le gestionnaire d’identifiants Git avant la prochaine publication depuis VS Code. Ne pas enregistrer de jeton dans le dépôt.

Références :
- [Déplacer les cartes et configurer un Board](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-board-layout)
- [Démarrer un Project](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/quickstart-for-projects)
- [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)
