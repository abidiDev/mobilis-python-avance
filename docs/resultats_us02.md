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
  du processus. Un essai sur un fichier artificiel 100 fois plus grand
  est nécessaire pour documenter la scalabilité avant le rendu.
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
- Il manque encore la démonstration de montée en charge **x100** avec
  des identifiants non répétés artificiellement, ainsi que la revue
  des conventions temporelles.
