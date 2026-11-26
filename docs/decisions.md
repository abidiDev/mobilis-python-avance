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

## 2026-11-25 — US-02 Trajets : décisions de nettoyage (proposées par B, à valider par A)

Constats mesurés sur `trajets_2026-08_2026-10.csv.gz` (155 631 lignes) :

| Anomalie | Lignes | Décision | Justification | Test |
|---|---:|---|---|---|
| Trois formats de date (ISO avec décalage, UTC `Z`, `JJ/MM/AAAA HH:MM:SS`) | 4 988 débuts et 5 305 fins au format français | Convertir en instant UTC ; format français interprété en `Europe/Paris` | Durées médianes du même ordre (20–37 min) quelle que soit la combinaison de formats : pas de décalage systématique observé | `test_trois_formats_de_dates` |
| Heure locale ambiguë (nuit du 25/10) | 0 | Première occurrence (`fold=0`), alerte | Aucun cas réel ; règle gardée pour un futur export | `test_heure_ambigue_signalee` |
| Heure locale inexistante (nuit du 29/03) | 0 | Ligne écartée | Instant impossible | `test_heure_inexistante_rejetee` |
| Même `trajet_id` répété | 620 (toutes des copies identiques) | Garder la 1re ligne valide, signaler `DOUBLON_IDENTIQUE` ; contenu différent → `ID_EN_CONFLIT` (0 cas) | Renvois de bornes (énoncé) ; R11 : facturé une seule fois | `test_dedoublonner_garde_la_premiere_occurrence` |
| Doublon écrit dans un autre format de date | 0 observé | Comparaison sur le trajet **normalisé** (empreinte BLAKE2b 16 octets) | Même instant = même trajet ; index plus compact qu'une ligne JSON | `test_renvoi_dans_un_autre_format_est_un_doublon_identique` |
| Fin antérieure au début | 145 signalements = 143 trajets uniques + 2 sur des lignes doublons (−1 à −59 min, toujours avec au moins une date ISO à décalage) | Conserver et signaler `DUREE_NEGATIVE` ; compté dans les départs/arrivées ; **non facturé** (R10) | La station et l'heure de départ restent plausibles ; cause non établie | `test_trajet_horodatage_incoherent_non_facture` (US-03) |
| Fin et station d'arrivée absentes | 78 | Conserver, compter `sans_retour`, exclure des arrivées ; pénalité R9 en facturation | Vélo non restitué : pas d'arrivée à inventer | `test_frequentation_weekend_et_retour_absent` |

Conventions d'analyse : matin = `[07h, 10h[`, soir = `[17h, 20h[`, heure civile `Europe/Paris`,
week-end = samedi et dimanche de la date locale.
