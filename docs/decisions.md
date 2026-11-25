# Décisions du projet

| Date | Décision | Motif |
|---|---|---|
| 2026-11-23 | Conserver le squelette officiel `src/` et `pyproject.toml` | Partir de la base fournie par le professeur |
| 2026-11-23 | Utiliser Python 3.11 en local et dans la CI | Version minimale officielle, déjà installée sur le PC |
| 2026-11-23 | Conserver les données en dehors du dépôt | Respecter la consigne du kit et préserver les exports |
| 2026-11-23 | GitHub Flow, revue croisée et contrôle `lint-type-test` | Garder `main` vérifiable et rendre les contributions lisibles |
| 2026-11-23 | Responsabilité par US : A Stations/API/Livraison ; B Trajets/Facturation | Chacun développe ses US de bout en bout, tests et documentation inclus ; revue croisée conservée |
| 2026-11-23 | Développement parallèle après accord #8 ; intégration finale commune | Éviter une attente artificielle entre API et facturation, tout en validant les échanges réels |

À compléter après exploration : modèles et signatures, gestion des anomalies,
stratégie de dédoublonnage, temps et fuseaux, choix de concurrence.

## 2026-11-23 — Noyau commun T-03 sur branche dédiée

Le package `src/mobilis/domain/` définit les objets immuables `Station`, `Trajet`,
`PeriodeAbonnement`, `TarifFormule`, `GrilleTarifaire` et
`ConfigurationTarifaire`. Les statuts de station, types de vélo et formules
d'abonnement sont des `StrEnum`. Le package `domain/anomalies.py` partage
`Anomalie`, `NiveauAnomalie`, `SignalerAnomalie` et un collecteur explicite.

Les adaptateurs s'engagent sur les ports de lecture de `domain/contracts.py`
(`SourceStations`, `SourceTrajets`, `SourceAbonnements`, `SourceTarifs`).
Un port de lecture fournit des objets normalisés et non un rapport métier.
Le service reçoit les objets normalisés ; la CLI assemble les deux.

**Décisions non validées :** stratégie finale des doublons, ambiguïté des dates
locales au passage à l'heure d'hiver, fin d'abonnement inclusive/exclusive,
traitement des trajets sans restitution et codes d'erreur HTTP.
Les signatures HTTP/facturation spécifiques ne sont pas figées avant lecture de
`serveur_bornes.py` et `specification_facturation.md`.

Voir [contrats_t03.md](contrats_t03.md) pour les définitions précises
et les tâches de validation du binôme. **PR de centralisation proposée,
validation du binôme attendue.**

## 2026-11-25 — US-01 Stations : décisions de nettoyage (proposées par B, à valider par A)

- `stations.csv` est lu en CP1252, séparateur `;`, décimales à virgule.
- Statuts normalisés vers `StatutStation` (`HS` = hors service) ; statut inconnu → ligne écartée.
- Capacité `NC` → `None` ; la station reste dans le référentiel mais n'est pas exploitable.
- Latitude inférieure à la longitude → colonnes permutées (2 cas, réseau vers 45,7° N / 4,8° E).
- Code répété → version la plus récemment mise en service retenue (3 codes).
- Station **exploitable** = en service **et** capacité connue (142 sur 150).

Détail chiffré et tests associés : [resultats_us01.md](resultats_us01.md).
