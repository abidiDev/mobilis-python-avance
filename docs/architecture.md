# Architecture Mobilis — version livrable

## Vue d'ensemble

Le produit est un **monolithe modulaire en Python 3.11+**, installable
avec `pip install .`. Il propose la commande `mobilis` et quatre sous-commandes :
`stations`, `frequentation`, `facturation`, `etat`.
Il ne fournit **aucun serveur web** : le serveur des bornes est un
simulateur HTTP externe fourni par l'enseignant.

```text
Utilisateur
    │ mobilis <commande> [--donnees ...] [--json] [--journal ...]
    ▼
src/mobilis/cli.py           Entrées, orchestration, code de sortie
    ├── adapters/            CSV CP1252, CSV.gz, JSONL, JSON, HTTP externe
    ├── services/            Référentiel, fréquentation, tarification, recettes, état
    └── domain/              Modèles, enum, contrats de lecture, anomalies
```

Les adaptateurs produisent des **objets du domaine** ; les services appliquent
des règles métier à ces objets ; la CLI compose les deux et présente le résultat.
Ni les services ni le domaine ne lisent directement de fichiers et ne font
d'appels HTTP. L'état d'une borne `EtatBorne` est déclaré dans `domain.models`
et reste réexporté depuis `services.etat_reseau` pour compatibilité.

## Flux de données réels

| Commande | Adaptateur principal | Service | Résultat |
|---|---|---|---|
| `mobilis stations` | `LecteurStationsCsv` | `construire_referentiel` | 150 codes distincts, 142 exploitables |
| `mobilis frequentation` | `LecteurTrajetsGzip` | `analyser_frequentation` | Flux horaires et soldes matin/soir |
| `mobilis facturation` | `LecteurTrajetsGzip`, abonnements JSONL, tarifs JSON, stations CSV | `MoteurFacturation`, `analyser_recettes` | Recettes par mois/formule, effet prix |
| `mobilis etat` | `ClientMobilisBornes`, stations CSV | `collecter_threads_avec_erreurs`, `comparer_etats` | Vides/pleines, écarts, absences |

### US-02 — Lecture en flux et dédoublonnage

1. `lire_lignes_brutes` décompresse le CSV.gz **ligne par ligne**.
2. `normaliser_lignes` convertit les valeurs, dates et types, avec diagnostics.
3. `dedoublonner` conserve la première ligne valide d'un `trajet_id`,
   en stockant une empreinte BLAKE2b du trajet **normalisé** dans un
   index **SQLite temporaire sur disque**.
4. `analyser_frequentation` agrège par heure, semaine/week-end,
   stations le matin et le soir. Les compteurs sont de taille bornée.
5. La mémoire RAM reste indépendante d'un chargement intégral du CSV ;
   en contrepartie, l'index SQLite croît sur disque avec le volume.

Le test officiel ×100 s'est achevé sur **15 563 100 lignes** avec
**15 501 100 trajets uniques**. Ce résultat précède l'optimisation
de l'empreinte en index ; ne pas lui attribuer les nouvelles dimensions
d'index ou un pic RSS non mesuré.

### US-03 — Tarification

Le moteur lit les trajets normalisés et les historiques d'abonnements,
sélectionne la grille à la **date locale** de début, applique R1–R12,
utilise `Decimal` et plafonne les abonnements par jour local.
Les recettes sont regroupées par mois et formule. Le contrefactuel
réutilise les mêmes trajets avec l'ancienne grille tarifaire.

### US-04 — Client HTTP résilient

`ClientMobilisBornes` utilise `X-Api-Key`, l'endpoint paginé `/stations`
et `/stations/{code}`. Le client gère les tentatives sur 429/503/504,
respecte un budget maximal pour l'attente `Retry-After`, et la
collecte `ThreadPoolExecutor` n'exécute jamais plus de **8 GET** simultanés.
Un échec HTTP définitif est signalé *par station*, sans stopper les autres.

Trois stratégies ont été comparées : séquentielle, threads et
`asyncio.to_thread`. Cette dernière utilise aussi des threads ;
ce n'est **pas** un client HTTP asynchrone natif.

Le simulateur peut présenter des codes supplémentaires ou des capacités
aléatoires différentes du CSV : la différence est **signalée**,
pas corrigée arbitrairement.

## Vérification et limites

La CI sur chaque PR exécute `ruff check`, `ruff format --check`,
`mypy --strict src/mobilis` et `pytest -q`.
Les tests unitaires utilisent des fichiers temporaires et un transport
HTTP injecté ; la recette réelle a été exécutée séparément sur le kit
et le serveur du professeur.

Limites assumées : non-détermination du simulateur en mode normal,
heures locales ambiguës, mesure du pic RSS ×100 historique manquante,
et temps de comparaison dépendant de l'ordonnancement et de l'état réseau.
Les décisions et leurs justifications sont dans [decisions.md](decisions.md).
