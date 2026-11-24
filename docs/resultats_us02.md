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
