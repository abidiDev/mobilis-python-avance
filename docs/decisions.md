# Décisions du projet

| Date | Décision | Motif |
|---|---|---|
| 2026-11-23 | Conserver le squelette officiel `src/` et `pyproject.toml` | Partir de la base fournie par le professeur |
| 2026-11-23 | Utiliser Python 3.11 en local et dans la CI | Version minimale officielle, déjà installée sur le PC |
| 2026-11-23 | Conserver les données en dehors du dépôt | Respecter la consigne du kit et préserver les exports |
| 2026-11-23 | GitHub Flow, revue croisée et contrôle `lint-type-test` | Garder `main` vérifiable et rendre les contributions lisibles |
| 2026-11-23 | Responsabilité par US : A Stations/API/Livraison ; B Trajets/Facturation | Chacun développe ses US de bout en bout, tests et documentation inclus ; revue croisée conservée |
| 2026-11-23 | Développement parallèle après accord #8 ; intégration finale commune | Éviter une attente artificielle entre API et facturation, tout en validant les échanges réels |

Note historique : ces points étaient ouverts le 23/11 ; les décisions effectives et
leurs justifications figurent dans les sections du 25 et du 26 novembre ci-dessous.

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

**État au 23/11 :** stratégie des doublons, ambiguïté DST, fin d'abonnement,
traitement de l'absence de restitution et retries HTTP encore ouverts.
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
| Fin antérieure au début | 145 alertes brutes (143 trajets uniques et 2 répétitions ; −1 à −59 min) | Conserver et signaler `DUREE_NEGATIVE` ; compté dans les départs/arrivées ; **non facturé** (R10) | La station et l'heure de départ restent plausibles ; cause non établie | `test_trajet_horodatage_incoherent_non_facture` (US-03) |
| Fin et station d'arrivée absentes | 78 | Conserver, compter `sans_retour`, exclure des arrivées ; pénalité R9 en facturation | Vélo non restitué : pas d'arrivée à inventer | `test_frequentation_weekend_et_retour_absent` |

Conventions d'analyse : matin = `[07h, 10h[`, soir = `[17h, 20h[`, heure civile `Europe/Paris`,
week-end = samedi et dimanche de la date locale.
## 2026-11-25 — US-03 Facturation : décisions d'interprétation (proposées par B, à valider par A)

La spécification `specification_facturation.md` est appliquée telle quelle ;
les points qu'elle ne tranche pas sont décidés ici et couverts par un test.

| Question | Décision | Test |
|---|---|---|
| Ordre des règles | R9 (pas de retour) → R10 (fin < début) → R9 (> 24 h) → R8 (fantôme) → R4–R7 | `test_r9_*`, `test_trajet_horodatage_incoherent_non_facture`, `test_r8_*` |
| « Plus de 24 h » | Strictement supérieur au seuil | `test_r9_penalite_hors_plafond[plus_de_24h]` |
| « Moins de 2 minutes » | Strictement inférieur | `test_r8_trajet_fantome_non_facture` |
| Formule d'un trajet pénalisé | Celle de R2/R3 ; la pénalité n'entre jamais dans le plafond | `test_r9_penalite_hors_plafond` |
| Plafond R6 | Par (abonné, jour local de début, formule) ; seules les formules d'abonnement | `test_exemples_valides_par_la_direction[E5]`, `test_r6_*` |
| Périodes qui se chevauchent | La plus récemment commencée l'emporte (0 cas dans le kit) | — |
| Abonnement inactif | Tarif occasionnel, compté mais non signalé (R3 ne signale que les introuvables) | `test_r2_abonnement_expire_donne_tarif_occasionnel` |
| Formule mal écrite (`" ANNUEL"`) | Corrigée et signalée en `info` | `test_abonnes_lignes_abimees_signalees_et_historique_conserve` |
| Tarifs invalides | Exception `TarifsInvalides` : on ne facture pas avec une grille partielle | `test_tarifs_invalides_refuses` |
| Mois des recettes | Mois de la date locale de début du trajet | `test_recettes_par_mois_et_formule` |
| Effet du 1er octobre | Mêmes trajets refacturés avec l'ancienne grille sur toute la période | `test_effet_prix_isole_le_changement_de_grille` |

Contrat de tarification : classe abstraite `Tarification` (patron Stratégie) et deux
implémentations, `TarificationAbonnement` (plafond R6) et `TarificationOccasionnelle`.
Une ABC plutôt qu'un `Protocol` : le calcul R4/R5/R7 est commun et vit dans la classe
de base ; seules les règles de plafond diffèrent.

Mémoire : le moteur traite un trajet à la fois. Le cumul du plafond est indexé par
abonné-jour (au plus ~5 200 abonnés × 92 jours), donc borné quel que soit le nombre de trajets.

Résultats chiffrés : [resultats_us03.md](resultats_us03.md).
## 2026-11-25 — US-01 Stations : décisions de nettoyage (proposées par B, à valider par A)

- `stations.csv` est lu en CP1252, séparateur `;`, décimales à virgule.
- Statuts normalisés vers `StatutStation` (`HS` = hors service) ; statut inconnu → ligne écartée.
- Capacité `NC` → `None` ; la station reste dans le référentiel mais n'est pas exploitable.
- Latitude inférieure à la longitude → colonnes permutées (2 cas, réseau vers 45,7° N / 4,8° E).
- Code répété → version la plus récemment mise en service retenue (3 codes).
- Station **exploitable** = en service **et** capacité connue (142 sur 150).

Détail chiffré et tests associés : [resultats_us01.md](resultats_us01.md).

## 2026-11-25 — Répartition effective des User Stories

Répartition constatée sur le Team Board et appliquée dans BACKLOG.md et CONTRIBUTING.md :
A (@abidiDev) — US-02 Trajets, US-04 État temps réel ; B (@plasticbagdancing) —
US-01 Stations, US-03 Facturation, US-05 Livraison. Les tâches #9–#11 et #19–#21
restent à réassigner sur GitHub en conséquence (à valider par A).


## 2026-11-26 — Décisions de clôture du travail métier et de revue

Les conventions proposées dans les sections US-01, US-02 et US-03 ont été
**examinées et acceptées par le responsable des US-02/US-04 (A)** dans le
cadre de la revue croisée. Elles constituent désormais les conventions
d'implémentation retenues, sous réserve de toute modification ultérieure
explicite demandée par l'enseignant.

1. **Station exploitable :** statut `en_service` et capacité connue.
   Une position GPS absente ne suffit pas à rejeter une station, car les
   quatre questions principales utilisent son identifiant et sa capacité.
   Les stations fermées/hors service restent présentes dans le référentiel
   complet pour éviter de les classer « inconnues » à tort.
2. **Codes de stations répétés :** retenir la version à date de mise en
   service la plus récente, garder l'historique des versions remplacées et
   consigner `CODE_REPETE`. À égalité, conserver la première.
3. **Trajets :** normaliser les trois formats temporels vers UTC ;
   agréger par date/heure `Europe/Paris`. Les 620 doublons sont ignorés
   après la première ligne valide. Pour une date locale ambiguë, `fold=0`
   et une alerte ; zéro cas dans le kit officiel.
4. **Durées négatives :** conserver le trajet pour les comptes de départ
   et d'arrivée, le signaler, mais ne pas le facturer (R10). Les 145
   signalements bruts représentent 143 trajets uniques, les deux autres
   appartenant à des répétitions. Les 78 trajets sans retour ne créent
   pas une arrivée fictive ; ils suivent la règle R9 en facturation.
5. **Ordre R8–R10 :** absence de retour (R9) ; fin antérieure au début
   (R10, prix nul) ; durée supérieure au seuil (R9) ; trajet fantôme
   (R8) ; tarification normale (R4–R7). Les pénalités restent hors
   plafond journalier.
6. **Abonnements :** bornes de dates inclusives, priorité à la période
   la plus récemment commencée en cas de chevauchement (aucun cas réel
   du kit) ; sans formule active, repli occasionnel. Plafond journalier
   par abonné, date locale et formule.
7. **API :** maximum 8 appels simultanés. Les 429, 503 et 504 sont
   réessayés selon une politique bornée ; si le serveur demande via
   `Retry-After` plus de 5 secondes, l'erreur est remontée plutôt que
   d'attendre indéfiniment ou d'envoyer un nouveau GET trop tôt. Les
   bornes indisponibles sont comptées à part, sans états inventés.
8. **Mesures :** distinguer le test ×100 des trajets (15 563 100 lignes,
   ancienne version avant index allégé), la RAM effectivement mesurée
   sur ×1 après refonte, et les 10,142 secondes observées pour l'API
   en mode normal avec 3 erreurs HTTP 504. Aucune de ces valeurs ne
   constitue une garantie universelle pour toute exécution future.
9. **Répartition définitive :** A (@abidiDev) : US-02 et US-04 ;
   B (@plasticbagdancing) : US-01, US-03 et US-05, avec relectures
   croisées et responsabilité commune de la soutenance.

**Traçabilité :** [PR #26](https://github.com/abidiDev/mobilis-python-avance/pull/26),
[PR #27](https://github.com/abidiDev/mobilis-python-avance/pull/27),
[PR #29](https://github.com/abidiDev/mobilis-python-avance/pull/29),
[PR #30](https://github.com/abidiDev/mobilis-python-avance/pull/30)
et leurs tests. L'acceptation de ces conventions par A ne vaut pas
une approbation GitHub au nom de B.
