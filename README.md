# Mobilis — Python avancé

Bibliothèque d'analyse d'un réseau de vélos en libre-service, réalisée en binôme.
Le dépôt contient pour le moment le squelette officiel et les outils de collaboration.
Les fonctionnalités métier et la commande `mobilis` restent à développer.

## Ouvrir le projet sous Windows

Dans Visual Studio Code : **Fichier > Ouvrir le dossier**, puis sélectionner :

```text
C:\Users\HP\Documents\projet pyton\mobilis
```

Ouvrir ensuite **Terminal > Nouveau terminal** (PowerShell).
Python 3.11 est installé sur ce PC ; `python` seul pointe actuellement vers 3.8.

## Installation

Lors du premier démarrage sur une machine, avec Python 3.11 installé :

```powershell
cd 'C:\Users\HP\Documents\projet pyton\mobilis'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
```

Si `.venv` existe déjà et fonctionne, ne pas le recréer.
L'utilisation du chemin complet de l'environnement évite d'avoir à modifier
la politique d'exécution PowerShell pour activer un script.
Chaque membre installe son propre environnement ; `.venv` n'est pas partagé sur GitHub.

## Vérifier avant une Pull Request

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy --strict src/mobilis
.\.venv\Scripts\python.exe -m pytest -q
```

La CI exécute ces mêmes contrôles sous Python 3.11 lors des PR vers `main`
et des envois sur `main`. Son contrôle s'appelle `lint-type-test`.
Le test de démarrage vérifie uniquement que le paquet s'importe : il ne valide
pas encore les fonctionnalités métier. La réussite locale ne remplace pas
le premier résultat réel de GitHub Actions après publication.

## État de la préparation au 23 novembre 2026

- Kit local comparé au ZIP officiel : contenu identique.
- Environnement `.venv` Python 3.11 créé et paquet installé.
- Ruff, vérification du formatage et mypy strict : réussis.
- Test officiel de démarrage : 1 test réussi.
- Compatibilité des dépendances installées : vérifiée avec `pip check`.
- Git initialisé sur `main` ; dépôt public : [abidiDev/mobilis-python-avance](https://github.com/abidiDev/mobilis-python-avance).
- [Premier passage GitHub Actions réussi](https://github.com/abidiDev/mobilis-python-avance/actions/runs/45147536773) sur le commit `71ca3d7`.
- [21 tickets créés](https://github.com/abidiDev/mobilis-python-avance/issues), avec critères, dépendances et répartition A/B.
- Project, protection de `main` et invitation du binôme : à finaliser.

## Fichiers et données

```text
projet pyton/
├── mobilis-kit.zip
├── mobilis-github-starter.zip
├── mobilis-kit/                  kit officiel conservé à part
│   ├── donnees/
│   ├── outils/serveur_bornes.py
│   ├── specification_facturation.md
│   └── demarrage/
└── mobilis/                      racine du dépôt à ouvrir
    ├── src/mobilis/
    ├── tests/
    ├── docs/
    ├── .github/
    ├── pyproject.toml
    └── README.md
```

Le dossier `src/mobilis` contient la bibliothèque ; `tests` contient ses tests.
Ne pas modifier les exports bruts et ne pas les versionner. Chaque membre
récupère le [kit officiel](https://dafniskra.github.io/portail_cours_M1/cours/PYTHON_AVANCE/projet_donnees/mobilis-kit.zip)
à côté de son dépôt. Les chemins seront fournis par les options de la future CLI.
Les règles R1–R12 et les exemples E1–E6 sont dans
`../mobilis-kit/specification_facturation.md`.

## Travailler en binôme

- [Règles de branches, PR et revue](CONTRIBUTING.md)
- [User Stories et tâches proposées](BACKLOG.md)
- [Création du dépôt et configuration du Project](GITHUB_PROJECT_SETUP.md)
- [Journal des décisions](docs/decisions.md)

Une tâche de développement a un responsable et l'autre membre pour relecteur.
Créer une branche courte à partir de `main`, ouvrir une PR liée à la tâche,
attendre la CI verte et la revue, puis fusionner et supprimer la branche.
Les [5 User Stories et 16 tâches](https://github.com/abidiDev/mobilis-python-avance/issues) sont créées et reliées. Le tableau Projects et la protection de `main` restent à configurer selon le guide.

Sujet de référence : [Projet final Mobilis](https://dafniskra.github.io/portail_cours_M1/cours/PYTHON_AVANCE/projet.html).
