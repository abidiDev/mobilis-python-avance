# US-02 — Mesure de la fréquentation (T-07/T-08)

## Exécution reproductible

Données brutes non versionnées. Installer le paquet puis exécuter :

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts/mesurer_frequentation.py "..\mobilis-kit\donnees\trajets_2026-08_2026-10.csv.gz"
```

Le script affiche les trajets valides uniques, les trajets sans retour, les
codes d'anomalies comptés, les cinq stations au plus fort solde sortant
matinal et les cinq au plus fort solde entrant du soir.

## Conventions / limites à relire à deux

- Les événements sont exprimés en heure civile **Europe/Paris**.
- Matin = `[07h, 10h[` ; soir = `[17h, 20h[`. Ces créneaux sont
  des conventions d'analyse, à confirmer avec le sujet/le binôme.
- Un trajet répété avec le même `trajet_id` est écarté après la première
  occurrence **valide**, via un index SQLite **sur disque temporaire**.
  Cela évite un `set` de tous les ID en RAM. Si un identifiant est
  réutilisé avec des contenus différents, on signale `ID_EN_CONFLIT`.
- Une date au format français sans fuseau est interprétée en
  `Europe/Paris`. Pour l'heure d'hiver ambiguë : `fold=0` avec
  une alerte ; les heures inexistantes sont rejetées.
- Une date de fin antérieure au début est signalée et le trajet est
  conservé pour les flux, sans prétendre qu'il est facturable.
- Les anomalies sont agrégées par **code** pour limiter la mémoire ;
  ce script ne produit pas de journal détaillé ligne par ligne.
- `tracemalloc` mesure le pic des allocations **Python tracées** ;
  il ne mesure ni le fichier SQLite temporaire ni toute la mémoire
  du processus. L'essai complet ×100 du 25/11/2026 est documenté ci-dessous.
- Les valeurs officielles ne doivent être annoncées qu'après une
  exécution du script sur les exports du kit, conservés hors Git.

## Pour le rapport

Conserver la sortie JSON, la commande exécutée, la taille du fichier
et le temps d'exécution mesuré sur la même machine ; joindre ensuite
le journal détaillé et les décisions de nettoyage au dossier final.

## Première exécution sur le jeu officiel — 24/11/2026

Ces nombres sont **retranscrits de la sortie exécutée par un membre du binôme
sur son poste Windows 11 / Python 3.11** ; ils doivent être reproduits lors
de la recette finale et ne constituent pas une validation indépendante.

Commande :

```powershell
.\.venv\Scripts\python.exe scripts/mesurer_frequentation.py "..\mobilis-kit\donnees\trajets_2026-08_2026-10.csv.gz"
```

| Indicateur | Valeur observée |
|---|---:|
| Trajets valides uniques | **155 011** |
| Doublons strictement identiques signalés | **620** |
| Durées négatives signalées | **145** |
| Trajets sans retour complet | **78** |
| Pic `tracemalloc` (allocations Python tracées) | **525 548 octets** |

Top 5 **stations qui se vident le matin** (solde arrivées moins départs) :

| Station | Solde |
|---|---:|
| MB-0142 | -1 801 |
| MB-0023 | -760 |
| MB-0133 | -608 |
| MB-0057 | -553 |
| MB-0144 | -480 |

Top 5 **stations qui se remplissent le soir** :

| Station | Solde |
|---|---:|
| MB-0142 | +1 397 |
| MB-0023 | +573 |
| MB-0133 | +565 |
| MB-0057 | +543 |
| MB-0144 | +447 |

Les agrégations couvrent **août à octobre cumulés** ; ce ne sont pas des
soldes instantanés ni des mesures par jour.

### Points à contrôler avant de déclarer US-02 terminée

- Les 145 durées négatives sont **signalées mais conservées** dans les
  flux. Définir/valider l'impact attendu sur les statistiques.
- Les 78 retours absents sont comptés séparément.
- Le volume total observé est cohérent avec l'audit préalable
  (`155 631 - 620 = 155 011`) ; ce rapprochement ne prouve pas à lui seul
  l'exactitude de chaque date ou agrégation.
- `tracemalloc` ne mesure **pas** la taille du fichier SQLite temporaire
  sur le disque ni la mémoire système totale. Mesurer aussi le temps, la
  taille du stockage temporaire et idéalement la mémoire du processus.
- L'essai ×100 a été exécuté le 25/11/2026 ; reste à relever la mémoire
  résidente sur Windows et à valider les conventions temporelles.

## Benchmark de scalabilité automatisé — outillage ajouté

Le script `scripts/benchmark_trajets.py` fabrique dans un **répertoire
temporaire** un vrai CSV.gz synthétique de taille ×1, ×2, ×10 ou ×100,
puis exécute **le vrai adaptateur `LecteurTrajetsGzip`** et **le vrai
service `analyser_frequentation`**. Les fichiers du kit restent inchangés ;
le fichier créé est supprimé automatiquement à la fin du processus.

Les IDs d'une copie reçoivent le suffixe `-S000`, `-S001`, etc.,
pour que les copies ne soient pas prises pour des doublons entre elles.
Les doublons qui existaient *à l'intérieur* du CSV original sont
conservés. Le code vérifie l'espace libre avant toute création.

### Validation automatique déjà exécutée

La CI GitHub teste le multiplicateur **×100 sur un petit jeu de test**
avec deux lignes sources : 200 lignes générées, 100 trajets uniques,
100 doublons et aucun fichier temporaire restant après analyse. Elle
vérifie également les sorties de `tracemalloc`, la taille de l'index
SQLite, le rejet des facteurs hors de [1,100] et l'absence de modification
du fichier source.

**Ce test ×100 sur un petit échantillon ne prouve pas encore le
traitement du fichier officiel multiplié par 100.** Un essai complet utilisant le fichier réel est maintenant consigné plus bas.

### Recette complète (sur le poste qui possède le kit)

Après `git switch feature/2-trajets` et `git pull --ff-only` :

```powershell
# Mesure de référence avec les mêmes outils et options :
.\.venv\Scripts\python.exe scripts/benchmark_trajets.py "..\mobilis-kit\donnees\trajets_2026-08_2026-10.csv.gz" --facteur 1

# Mesure x100 : écrire automatiquement le rapport JSON hors du dépôt :
.\.venv\Scripts\python.exe scripts/benchmark_trajets.py "..\mobilis-kit\donnees\trajets_2026-08_2026-10.csv.gz" --facteur 100 > "..\mobilis-benchmark-x100.json"
```

Le benchmark x100 est gourmand en calculs et occupe **potentiellement
plusieurs Go de stockage temporaire** pendant son exécution ; ne pas
le lancer sur un disque presque plein. `--tracemalloc` est facultatif :
il ralentit sensiblement le programme. Sans lui, le script donne
le **pic RSS du processus** ; il ne faut pas confondre RSS, allocations
tracées par `tracemalloc` et taille de l'index SQLite.

La référence sur le fichier officiel présentée plus haut a été mesurée
par un membre sur son poste avec `tracemalloc` : **52,814 secondes**.
Les temps entre deux exécutions ne sont comparables que si les mêmes
options de mesure sont utilisées.

### Valeurs attendues pour le CSV officiel répété 100 fois

Si le jeu source est identique et qu'aucune nouvelle anomalie ne se crée
par la réécriture des IDs :

- **15 563 100** lignes de données synthétiques (155 631 × 100).
- **15 501 100** trajets uniques (155 011 × 100).
- **62 000** doublons exacts (620 × 100).
- **14 500** durées négatives détectées (145 × 100).

Ces valeurs ont été **confirmées par l'exécution réelle ×100 du 25/11/2026**.
Les stations doivent garder les mêmes classements : leurs soldes
sont multipliés par 100 si toutes les données se retrouvent.

### Critères de clôture

- [x] Pipeline GZIP, normalisation, doublons et statistiques opérationnels
      sur le fichier officiel (une exécution documentée).
- [x] Tests fonctionnels et tests synthétiques x100 sur petit échantillon.
- [x] Ruff, formatage, mypy strict et pytest vérifiés en CI.
- [x] Exécuter le stress test **×100 complet** et conserver les chiffres de
      temps, fichiers et index SQLite (mesure RAM non disponible dans ce test).
- [ ] Vérifier la mesure du pic RSS avec le correctif Windows, et documenter
      l'évolution de la mémoire sur une exécution mesurée.
- [ ] Valider en binôme les conventions de dates, créneaux, doublons et
      traitement des durées négatives.
- [ ] Revue croisée de la PR puis fusion après validation.

## Recette complète ×100 exécutée sur Windows — 25/11/2026

Les valeurs suivantes proviennent de la **sortie du script envoyée par
l'utilisateur**, après exécution locale sur le fichier officiel multiplié
100 fois. Ce ne sont ni une extrapolation ni un test CI de 200 lignes.

| Mesure | Observation |
|---|---:|
| Lignes synthétiques | **15 563 100** |
| Trajets uniques | **15 501 100** |
| Doublons strictement identiques | **62 000** |
| Durées négatives signalées | **14 500** |
| Temps de génération | 187,069 s |
| Temps d'analyse | **1 280,943 s** (21 min 20,943 s) |
| Temps génération + analyse | 1 468,012 s (24 min 28,012 s) |
| Index de dédoublonnage SQLite | **2 930 905 088 octets** (~2,73 Gio) |
| CSV.gz synthétique | **461 392 647 octets** (~440 Mio) |
| Espace disque libre avant | 27 794 538 496 octets |
| Nettoyage automatique | Vrai |

Les trois comptages (trajets uniques, doublons, durées négatives)
correspondent exactement à ×100 par rapport au jeu officiel.
La mémoire Python tracée est `null` car l'option
`--tracemalloc` **n'était pas activée** lors de cet essai.
Le pic RSS du processus est également `null` : **le premier
instrument Windows n'a pas rapporté de valeur exploitable**.
Par conséquent, **le stress-test complet a fonctionné, mais il ne
permet pas d'affirmer une consommation RAM mesurée et constante**.

Correctif ajouté à `scripts/benchmark_trajets.py` : déclaration
explicite des signatures WinAPI (types du HANDLE, pointeur du
`PROCESS_MEMORY_COUNTERS` et type du résultat) et vérification de
la disponibilité du compteur Windows avant un long lancement.
Ce correctif doit être testé **sur la machine Windows**, la CI Linux
ne pouvant valider l'appel à l'API native Windows.

**Vérification rapide sur Windows, sans refaire le test ×100** :

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -c "from scripts.benchmark_trajets import _pic_rss_octets; print(_pic_rss_octets())"
```

Le résultat attendu est un nombre entier **strictement positif**
(en octets). Une valeur positive obtenue après ce correctif ne
rétroconstitue pas rétroactivement le pic RAM du test ×100.
Pour montrer la stabilité mémoire, comparer des mesures RSS réelles
sur des tailles différentes, par exemple ×1, ×2 et ×10, et expliquer
la dépendance au stockage SQLite temporaire (2,73 Gio en ×100).

Pour clôturer US-02 : valider les conventions de nettoyage et
les créneaux avec le binôme, obtenir sa revue de la PR, puis
fusionner lorsque ces points auront été acceptés.

## Revérification indépendante par B — 25/11/2026 (après découpage du pipeline)

Exécution sur le poste de B (Windows 11, Python 3.11.9), kit officiel non modifié,
avec le lecteur découpé en trois générateurs et l'empreinte BLAKE2b du trajet normalisé.

`mesurer_frequentation.py` : **155 011** trajets uniques, **620** `DOUBLON_IDENTIQUE`,
**145** `DUREE_NEGATIVE`, **78** sans retour, mêmes cinq stations et mêmes soldes
que ci-dessus ; pic `tracemalloc` **529 505 octets**.

`benchmark_trajets.py --facteur 1` (sans `tracemalloc`) :

| Mesure | Valeur |
|---|---:|
| Temps d'analyse | **7,227 s** |
| Pic RSS du processus (correctif WinAPI) | **32 866 304 octets** (~31 Mio) |
| Index SQLite de dédoublonnage | **8 130 560 octets** (~7,8 Mio) |

L'index stocke désormais 16 octets par trajet au lieu de la ligne JSON complète :
l'ancien index ×100 mesurait 2 930 905 088 octets, soit ~29,3 Mo par copie du fichier,
contre ~8,1 Mo ici. Le correctif RSS Windows renvoie bien une valeur positive.
Reste à mesurer le RSS sur ×2 et ×10 pour montrer qu'il ne croît pas avec la taille.
