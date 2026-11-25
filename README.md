# Mobilis — Python avancé

Bibliothèque Python commune pour analyser le réseau fictif de vélos en libre-service
Mobilis : référentiel des stations, fréquentation, facturation et état temps réel
des bornes. Projet de binôme du cours *Python avancé*
([sujet](https://dafniskra.github.io/portail_cours_M1/cours/PYTHON_AVANCE/projet.html)).

## Installation

Python **3.11** ou plus récent. Depuis la racine du dépôt (PowerShell) :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Pour un simple usage, sans outils de développement : `pip install .`
L'installation crée la commande `mobilis` (`.\.venv\Scripts\mobilis.exe`).
Seule dépendance d'exécution : `tzdata` sous Windows (fuseau Europe/Paris).

Vérification sur un environnement vierge (25/11/2026, Windows 11, Python 3.11.9) :
nouveau venv, `pip install .`, puis `mobilis --version` et `mobilis facturation`
donnent les mêmes résultats que l'environnement de développement.

## Données

Les fichiers du [kit officiel](https://dafniskra.github.io/portail_cours_M1/cours/PYTHON_AVANCE/projet_donnees/mobilis-kit.zip)
ne sont **pas versionnés** et ne sont **jamais modifiés à la main**. Décompresser le kit
à côté du dépôt, puis indiquer le dossier `donnees/` :

```powershell
$env:MOBILIS_DONNEES = "..\mobilis-kit\donnees"   # ou --donnees DOSSIER à chaque commande
```

Chaque fichier peut aussi être donné explicitement : `--stations`, `--trajets`,
`--abonnes`, `--tarifs`.

## Commandes

| Commande | Question traitée | Durée indicative |
|---|---|---:|
| `mobilis stations` | Quelles stations sont réellement exploitables ? Quelles anomalies ? | < 1 s |
| `mobilis frequentation` | Quelles stations se vident le matin et se remplissent le soir ? Profil horaire semaine / week-end ? | 4 s (63 s avec `--memoire`) |
| `mobilis facturation` | Recettes mensuelles par formule et effet du changement tarifaire du 1er octobre 2026 | 22 s |
| `mobilis etat` | État temps réel des bornes, stations vides / pleines, écarts avec le référentiel | 10 s |

Options communes : `--json` (sortie complète en JSON), `--journal FICHIER.csv`
(journal détaillé des anomalies, une ligne par anomalie).

`mobilis etat` interroge le simulateur du kit, à lancer dans un second terminal :

```powershell
python ..\mobilis-kit\outils\serveur_bornes.py            # conditions réelles
python ..\mobilis-kit\outils\serveur_bornes.py --calme    # pour comparer les stratégies
mobilis etat --comparer-strategies
```

Codes de sortie : `0` succès, `1` données absentes ou invalides, `2` usage incorrect,
`3` API des bornes injoignable.

## Résultats sur le kit officiel

| Cas | Résultat principal | Détail |
|---|---|---|
| Stations | 153 lignes → 150 stations, **142 exploitables** | [resultats_us01.md](docs/resultats_us01.md) |
| Trajets | 155 631 lignes → **155 011 trajets** (620 doublons) ; MB-0142 se vide le plus le matin (−1 801) | [resultats_us02.md](docs/resultats_us02.md) |
| Facturation | **249 166,70 €** sur le trimestre ; effet prix d'octobre **+16 076,65 € (+20,7 %)** | [resultats_us03.md](docs/resultats_us03.md) |
| État temps réel | 149 bornes, 146 réponses en **10,1 s** (< 15 s), 8 requêtes simultanées au plus | [resultats_us04.md](docs/resultats_us04.md) |

Chaque chiffre se reproduit avec la commande correspondante. Les décisions de
nettoyage (anomalie, quantité, décision, justification, test) sont dans
[docs/decisions.md](docs/decisions.md).

## Architecture

Monolithe modulaire en couches ([docs/architecture.md](docs/architecture.md)) :

```text
src/mobilis/
├── cli.py         orchestration : arguments, assemblage, affichage
├── domain/        modèles immuables, anomalies, ports de lecture (Protocol)
├── adapters/      CSV, CSV.gz, JSONL, JSON, client HTTP des bornes
└── services/      règles métier : stations, fréquentation, facturation, recettes, état
```

Les services reçoivent des objets du domaine, jamais des chemins de fichiers ;
la CLI assemble adaptateurs et services.

## Qualité

| Contrôle | Commande | État |
|---|---|---|
| Lint | `python -m ruff check .` | vert |
| Formatage | `python -m ruff format --check .` | vert |
| Typage | `python -m mypy --strict src/mobilis` | vert (0 erreur) |
| Tests | `python -m pytest -q` | **127 tests** (12 paramétrages, mocks HTTP et CLI) |

La CI GitHub Actions (`lint-type-test`) exécute ces contrôles sous Python 3.11 à
chaque PR vers `main`. Les tests n'utilisent ni le kit ni le serveur : ils écrivent
de petits fichiers synthétiques et simulent l'API.

## Travailler en binôme

- [Règles de branches, PR et revue](CONTRIBUTING.md)
- [User Stories et tâches](BACKLOG.md)
- [Journal des décisions](docs/decisions.md)

Répartition : @abidiDev — Trajets (US-02) et État temps réel (US-04) ;
@plasticbagdancing — Stations (US-01), Facturation (US-03) et Livraison (US-05).
Chaque PR est relue par l'autre membre avant fusion.
