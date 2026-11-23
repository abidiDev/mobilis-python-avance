# Starter GitHub pour le projet Mobilis

Ce pack contient **seulement les fichiers de gestion de projet et de CI**. Il ne remplace pas le squelette `demarrage/` du kit officiel.

Le squelette et ce starter sont maintenant assemblés localement. Pour ce PC, suivre d’abord le [README Windows](README.md). Les tickets et le Project restent à créer sur GitHub.

## Mode d'emploi
1. Télécharger et décompresser le kit Mobilis officiel.
2. Initialiser un dépôt avec le contenu du répertoire `demarrage/`.
3. Copier les fichiers de ce pack à la racine du dépôt, en conservant `.github/`.
4. Vérifier dans le `pyproject.toml` que `[project.optional-dependencies]` contient `dev = ["pytest", "mypy", "ruff", ...]`. Adaptez selon les dépendances déjà présentes dans le squelette.
5. Utiliser Python 3.11, choisi pour cet environnement et la CI. Le Python système 3.8 ne convient pas. Exécuter les commandes avec `.\.venv\Scripts\python.exe` comme dans le README.
6. Ne pas versionner les fichiers bruts du dossier `donnees/`, conformément à la consigne de non-versionnement des données. Garder les documents de spécification et le simulateur à disposition pour le développement ; leur éventuel partage dans le dépôt dépend des consignes de votre enseignant.
7. Créer le Project et ses Issues à partir de `GITHUB_PROJECT_SETUP.md` et `BACKLOG.md`.
8. La CI s'exécute automatiquement pour chaque PR vers `main`.

Attention : les critères de la CI sont volontairement stricts ; leur premier passage nécessite du code de base, des tests et la bonne configuration de `pyproject.toml`.
