# Bilan individuel — Wael (US-02 et US-04)

## Rôle et responsabilité

Dans le projet Mobilis de Python avancé, j'ai pris en charge
**US-02 — Trajets / Fréquentation** et **US-04 — État temps réel**.
Ma binôme a pris en charge le référentiel de stations (US-01),
la facturation (US-03) et la livraison en ligne de commande (US-05).
Nous avons défini des contrats partagés et effectué des relectures croisées.

## US-02 — Concevoir un traitement de données qui passe à l'échelle

Le défi principal était de traiter un fichier `CSV.gz` contenant
des trajets, alors que le jeu de données pouvait être multiplié par cent.
J'ai utilisé un **pipeline de générateurs** pour décompresser,
normaliser puis dédoublonner les lignes sans charger le fichier entier
en mémoire.

Les instants issus de plusieurs formats sont convertis vers UTC,
avec `Europe/Paris` pour les statistiques locales. Les doublons
sont écartés après la première ligne valide à l'aide d'un index
**SQLite temporaire**, plus prévisible en RAM qu'un dictionnaire
de tous les trajets. Une revue croisée a ensuite conduit à stocker
des **empreintes BLAKE2b de 16 octets**, plutôt que les données complètes.
J'ai participé à la vérification des résultats et à la documentation
des anomalies (doublons, absence de retour, durée négative).

Sur le fichier officiel : **155 631 lignes**, **155 011 trajets uniques**,
**620 doublons**, **145 signalements de durée négative** dont
**143 trajets distincts**, **78 trajets sans retour**. La station
`MB-0142` présente le solde matinal le plus négatif (**−1 801**).
Le test de charge ×100 complet a traité **15 563 100 lignes**,
dont **15 501 100 trajets uniques**, en **1 280,943 s** pour la phase
d'analyse sur la version d'index antérieure à l'optimisation.

## US-04 — Collecter un état réseau malgré les pannes

J'ai implémenté un client HTTP consommant le simulateur officiel
avec l'en-tête `X-Api-Key`, la pagination et le mapping des
vélos mécaniques/électriques, places libres et horodatage.
La contrainte majeure était de ne jamais dépasser **8 requêtes
simultanées**, tout en gérant les erreurs **429, 503 et 504**.

La collecte concurrente conserve les états valides si certaines bornes
ne répondent pas. Le décorateur de retry utilise `Retry-After` mais
**abandonne** lorsque l'attente demandée dépasse le budget prévu,
pour ne pas bloquer le programme indéfiniment. Après revue croisée,
le comparatif des trois stratégies a aussi été rendu tolérant aux
pannes d'une borne.

Lors d'une recette réelle en mode normal, **149 bornes ont été listées**,
**146 réponses** obtenues, **3 bornes** signalées en 504, pour
une durée totale de **10,142 s**, sous le seuil de 15 secondes.
En mode calme, la collecte principale a pris **0,829 s**.
Le comparatif mesuré sur une exécution a donné
**0,529 s** (séquentiel), **0,562 s** (threads) et
**0,229 s** (`asyncio.to_thread`) : ces valeurs ne constituent pas
un classement universel.

## Démarche de qualité et travail d'équipe

J'ai combiné tests de parsing, de gestion d'anomalies, de normalisation
des dates, de concurrence, de retries et de robustesse HTTP.
Les contrôles automatisés de GitHub Actions sont
`pytest`, `ruff check`, `ruff format --check` et
`mypy --strict`. Sur la branche d'intégration regroupant les cinq US,
la CI a atteint **139 tests réussis** lors de la première synchronisation
des correctifs (la version finale doit être vérifiée à nouveau après
chaque changement).

Le travail en binôme m'a permis de pratiquer la séparation
des responsabilités, les PR, la revue de code et la justification
des décisions dans `docs/decisions.md`. Les corrections réciproques
ont porté notamment sur la structure des générateurs, le coût de
l'index, la gestion de `Retry-After` et le comportement face aux 504.

## Difficultés, limites et recul personnel

La difficulté la plus instructive a été de distinguer **la justesse
fonctionnelle** (comptages corrects et tests verts) de **la performance
réelle** (temps, mémoire, espace disque). Un test ×100 réussi ne
démontre pas à lui seul un pic RAM constant : il faut mesurer
la mémoire du processus et celle de l'index SQLite séparément.

En HTTP, les erreurs transitoires et la variabilité du simulateur
rendent les mesures instables. J'ai appris à isoler une panne d'une
station sans interrompre toute la collecte et à ne pas comparer
naïvement des chronométrages pris dans des conditions différentes.

Enfin, j'ai renforcé ma compréhension des générateurs Python,
du protocole HTTP, de `ThreadPoolExecutor`, de l'orchestration
`asyncio.to_thread`, de la typage strict et de la CI.

## Conclusion

Mes deux US remplissent les fonctions attendues et disposent de
résultats sur le kit réel ainsi que de tests automatisés.
La livraison commune nécessite également l'intégration des US
de ma binôme, la revue croisée et la préparation de notre soutenance.
