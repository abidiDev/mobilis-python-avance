# US-01 — Référentiel des stations (T-04, T-05, T-06)

## Commande reproductible

En attendant `mobilis stations` (#19), depuis la racine du dépôt :

```powershell
.\.venv\Scripts\python.exe scripts/mesurer_stations.py "..\mobilis-kit\donnees\stations.csv"
```

Exécution du 25/11/2026 sur le poste de B (Windows 11, Python 3.11.9), kit non modifié.

## Résultat

| Indicateur | Valeur |
|---|---:|
| Lignes lues (versions de stations) | **153** |
| Lignes écartées | **0** |
| Stations dans le référentiel (un code = une station) | **150** |
| En service / hors service / fermées | 144 / 3 / 3 |
| **Stations exploitables** (en service et capacité connue) | **142** |

Stations non exploitables : MB-0013, MB-0047, MB-0105 (fermées) ; MB-0019, MB-0113,
MB-0143 (hors service) ; MB-0028, MB-0090 (capacité « NC »).

## Journal des anomalies

| Code | Niveau | Lignes | Décision | Justification | Test |
|---|---|---:|---|---|---|
| Encodage CP1252 | — | toutes | Lu avec `encoding="cp1252"`, séparateur `;` | Export d'un ancien outil Windows : en UTF-8, les accents sont illisibles | `test_encodage_cp1252_et_accents` |
| `STATUT_NON_NORMALISE` | info | 110 | Corrigé vers l'`Enum` (`En service `, `EN SERVICE`, `HS`, `FERMEE`…) | 7 écritures pour 3 statuts, sans ambiguïté | `test_normalisation_des_statuts` |
| `ESPACES_SUPERFLUS` | info | 8 (4 noms, 4 capacités) | Espaces retirés | Aucune perte d'information | `test_valeurs_corrigees` |
| `DATE_FORMAT_ISO` | info | 6 | Lu en `AAAA-MM-JJ` | Format non ambigu, différent du `JJ/MM/AAAA` majoritaire | `test_valeurs_corrigees` |
| `CAPACITE_INCONNUE` | alerte | 2 (MB-0028, MB-0090) | `capacite=None`, station conservée mais **non exploitable** | Valeur `NC` : ne pas inventer de capacité | `test_referentiel_de_bout_en_bout` |
| `COORDONNEES_INVERSEES` | alerte | 2 (MB-0064, MB-0135) | Colonnes permutées puis conservées | Latitude ≈ 4,8 et longitude ≈ 45,7 : impossible pour un réseau situé vers 45,7° N / 4,8° E | `test_valeurs_corrigees` |
| `COORDONNEES_ABSENTES` | alerte | 1 (MB-0109) | `None`, station toujours exploitable | Les coordonnées ne servent ni à la facturation ni à l'état des bornes | `test_valeurs_corrigees` |
| `CODE_REPETE` | alerte | 3 codes (MB-0033, MB-0068, MB-0104) | Version de mise en service la plus récente retenue | Même nom et mêmes coordonnées, nouvelle capacité ou remise en service (MB-0068 : hors service en 2017, en service en 2026) | `test_referentiel_de_bout_en_bout`, `test_version_ancienne_lue_apres_la_recente` |
| `LIGNE_REJETEE` | erreur | 0 | Ligne écartée (code, statut ou date illisible) | Aucune valeur fiable pour construire la station | `test_lecture_ne_s_arrete_pas_et_compte_chaque_anomalie` |

## Choix de conception

- `Station` valide ses invariants dans `__post_init__` (dataclass `frozen`) :
  un objet `Station` existant est toujours cohérent, y compris après `dataclasses.replace`.
- Le format `MB-XXXX` est contrôlé par le lecteur, pas par le modèle : d'autres
  sources (tests, API des bornes) peuvent construire des stations.
- Le lecteur émet **toutes** les versions ; le service `construire_referentiel`
  décide de la version retenue. Ainsi, la règle de dédoublonnage se teste sans fichier.
- `RapportStations.exploitables` est un `tuple[Station, ...]` sans doublon :
  c'est l'entrée attendue par `comparer_etats` (US-04) et par la règle R12 (US-03).
