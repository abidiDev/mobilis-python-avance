# US-03 — Facturation et recettes (T-09, T-10, T-11)

## Commande reproductible

Données brutes non versionnées (`../mobilis-kit/donnees`). Le script utilise aussi
le lecteur de trajets de l'US-02 (PR #26) :

```powershell
.\.venv\Scripts\python.exe scripts/mesurer_facturation.py "..\mobilis-kit\donnees"
```

Exécution du 25/11/2026 sur le poste de B (Windows 11, Python 3.11.9), code des
branches US-02 et US-03 fusionnées localement : **21,8 s** pour deux passes complètes
(grille réelle, puis ancienne grille). 63 tests, Ruff et mypy strict verts sur ce code.

## Recettes mensuelles par formule (€, date locale de début)

| Mois | Annuel | Mensuel | Solidaire | Occasionnel | **Total** |
|---|---:|---:|---:|---:|---:|
| Août 2026 | 15 210,50 | 5 321,50 | 539,25 | 41 882,80 | **62 954,05** |
| Septembre 2026 | 20 711,00 | 7 903,00 | 1 007,75 | 62 702,00 | **92 323,75** |
| Octobre 2026 | 21 032,20 | 8 055,60 | 1 032,75 | 63 768,35 | **93 888,90** |
| **Trimestre** | | | | | **249 166,70** |

Les pénalités de non-restitution (R9) sont incluses dans la formule du trajet.

## Changement tarifaire du 1er octobre 2026

Méthode : refacturer **les mêmes trajets, avec les mêmes abonnés**, en appliquant
l'ancienne grille sur toute la période (`avec_grille_unique`). L'écart d'octobre mesure
donc l'effet du seul changement de prix, sans effet de volume.

| Octobre 2026 | Annuel | Mensuel | Solidaire | Occasionnel | **Total** |
|---|---:|---:|---:|---:|---:|
| Recettes réelles (nouvelle grille) | 21 032,20 | 8 055,60 | 1 032,75 | 63 768,35 | **93 888,90** |
| Si l'ancienne grille s'appliquait | 17 989,50 | 6 938,00 | 1 032,75 | 51 852,00 | **77 812,25** |
| **Effet prix** | +3 042,70 | +1 117,60 | 0,00 | +11 916,35 | **+16 076,65** |

- L'effet prix d'octobre est de **+16 076,65 €, soit +20,7 %** par rapport à l'ancienne grille.
- La formule solidaire n'a pas changé de tarif : écart nul, ce qui valide la méthode.
- Le volume d'octobre (51 694 trajets) est inférieur à celui de septembre (61 774) ;
  sans hausse de prix, octobre aurait rapporté 77 812,25 € au lieu de 92 323,75 €
  en septembre. La hausse de recettes d'octobre vient donc des prix, pas du volume.

Trajets par mois et formule :

| Mois | Annuel | Mensuel | Solidaire | Occasionnel | Total |
|---|---:|---:|---:|---:|---:|
| Août | 19 535 | 6 501 | 2 767 | 12 740 | 41 543 |
| Septembre | 29 047 | 9 613 | 4 155 | 18 959 | 61 774 |
| Octobre | 24 037 | 8 123 | 3 637 | 15 897 | 51 694 |

## Statuts de facturation (155 011 trajets uniques)

| Statut | Trajets | Règle |
|---|---:|---|
| Facturé | 152 810 | R4–R7 |
| Fantôme (< 2 min, retour à la station de départ) | 1 944 | R8 — à transmettre à la maintenance |
| Pénalité de non-restitution (150 €) | 114 | R9 — 78 sans retour + 36 de plus de 24 h |
| Horodatage incohérent (fin < début) | 143 | R10 — non facturé |

Plafond journalier R6 : les abonnés annuels ont économisé 749,50 € (août),
1 340,50 € (septembre) et 1 187,60 € (octobre). Aucun plafond atteint
pour les formules mensuelle et solidaire.

## Journal des anomalies propres à la facturation

| Code | Nombre | Décision | Justification |
|---|---:|---|---|
| `abonnes.jsonl:JSON_INVALIDE` | 9 | Ligne écartée | Lignes vides ou tronquées à l'export ; aucune valeur fiable à récupérer |
| `abonnes.jsonl:FORMULE_NON_NORMALISEE` | 147 | Corrigée (`strip().lower()`) | `" annuel"`, `"ANNUEL"`, `"Mensuel"`… désignent sans ambiguïté une formule connue |
| `ABONNE_INTROUVABLE` | 203 trajets | Tarif occasionnel, signalé | R3 |
| Abonnement inactif à la date du trajet | 702 trajets | Tarif occasionnel | R3 (abonnement expiré ou pas encore commencé) |
| `HORODATAGE_INCOHERENT` | 143 trajets | Non facturé | R10 ; 145 signalements dans le lecteur dont 2 sur des lignes doublons |
| `STATION_INCONNUE` | 111 occurrences | Facturé normalement, signalé | R12 ; référentiel lu par code, en attendant le lecteur complet de l'US-01 |
