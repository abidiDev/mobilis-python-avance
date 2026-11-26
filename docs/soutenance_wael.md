# Fiche de soutenance — partie Wael

**Objectif :** environ dix minutes sur les diapositives 4, 5, 7,
8, 11, 12 et 15. Ce document est un support oral : ne pas le lire
mot à mot. Laisser de la place à la démonstration commune.

## Diapo 4 — Architecture (≈ 1 min 20)

« Nous avons choisi un monolithe modulaire, pas des microservices.
La CLI orchestre les appels ; les adaptateurs lisent les fichiers
et l'API externe ; les services appliquent les règles métier ;
le domaine porte les modèles et les contrats communs.
Cette séparation permet de tester les calculs sans avoir besoin
du serveur HTTP ni du jeu officiel. »

**Question probable :** pourquoi un adaptateur ? Pour isoler les
formats externes de la logique métier et pouvoir simuler la source
dans les tests.

## Diapo 5 — Contrats communs (≈ 1 min)

« Nous échangeons des objets dataclass typés, comme `Station`,
`Trajet`, `PeriodeAbonnement` et `EtatBorne`. Les ports de lecture
utilisent des `Protocol`. Les anomalies ont un modèle commun :
fichier, ligne, identifiant, catégorie, décision. Ce langage partagé
a rendu l'intégration des quatre commandes possible. »

**Expliquer :** un `Protocol` fixe ce que sait faire un lecteur,
pas sa technologie interne.

## Diapo 7 — Trajets en flux (≈ 1 min 30)

« Notre difficulté était un CSV.gz de 155 631 lignes, à multiplier
par 100. Nous utilisons trois générateurs : lire, normaliser,
dédoublonner. On ne charge pas tout le CSV. Pour dédupliquer, un
index SQLite temporaire sur disque mémorise un ID et une empreinte
BLAKE2b du trajet normalisé. Ainsi deux formats de date décrivant
le même instant donnent le même trajet logique. »

**Chiffres :** 155 011 trajets uniques ; 620 doublons.
Test ×100 : 15 563 100 lignes, 15 501 100 uniques.

## Diapo 8 — Fréquentation (≈ 1 min)

« Nous convertissons les instants en heure locale Europe/Paris,
puis agrégeons les départs et arrivées par station, matin/soir,
et les profils horaires semaine ou week-end. Le solde est
arrivées moins départs : négatif, la station se vide ;
positif, elle se remplit. »

**Exemple :** MB-0142, solde matinal −1 801.

## Diapo 11 — État temps réel (≈ 1 min 40)

« L'API du simulateur exige X-Api-Key, une pagination, et pas
plus de huit requêtes simultanées. Nous utilisons
ThreadPoolExecutor. Un décorateur gère 429, 503, 504
avec Retry-After et un budget d'attente. Une station
en panne n'empêche pas les autres de répondre. »

**Mesure réelle :** 149 codes, 146 réponses et 3 HTTP 504,
en 10,142 secondes (objectif moins de 15 secondes).
En mode calme : collecte complète en 0,829 s.
La comparaison séquentiel / threads / asyncio.to_thread est
indicative ; asyncio.to_thread n'est pas un vrai client HTTP
asynchrone natif.

## Diapo 12 — Qualité (≈ 1 min 20)

« Nous avons des tests unitaires qui n'ont pas besoin du kit,
des tests de limites de concurrence, des cas de date ambiguë
et des anomalies, ainsi qu'une CI GitHub qui vérifie Ruff,
le formatage, mypy strict et pytest. La branche d'intégration
a compté 139 tests verts après synchronisation des US. »

**Distinction :** les tests automatiques vérifient surtout la
justesse ; le benchmark mesure temps, mémoire et disque,
sur le vrai kit et le simulateur officiel.

## Diapo 15 — Recul et limites (≈ 1 min 20)

« Trois enseignements : un pipeline peut être correct mais lent ;
une mesure x100 ne prouve pas sans compteur RSS la stabilité de
la mémoire ; et les erreurs 504 ou les capacités aléatoires
du simulateur doivent être affichées, pas cachées.
Nous avons amélioré l'index et corrigé les politiques de retry
grâce aux revues croisées. »

**Savoir répondre :**
- Pourquoi SQLite ? Empêcher un set Python d'IDs de grossir avec le CSV.
- Pourquoi 143 incohérents mais 145 alertes ? Deux alertes concernent
  des trajets dupliqués.
- Pourquoi 150 stations CSV contre 149 bornes API ? Ce sont deux
  sources distinctes ; le rapprochement identifie les écarts.
- Pourquoi pas asyncio natif ? `asyncio.to_thread` enveloppe
  le transport HTTP synchrone ; comparaison honnête, pas promesse
  d'entrées/sorties non bloquantes natives.

## Démo à deux

Lancer le serveur des bornes dans un terminal. Dans un autre,
utiliser `mobilis stations`, `mobilis frequentation`,
`mobilis facturation` et `mobilis etat` avec le dossier du kit.
Prévoir les fichiers à l'avance et présenter les résultats
réels, sans supposer qu'une borne hors ligne répondra.
