# US-04 — API bornes : état technique et validation

## Fonctionnalités réellement codées

- `adapters/bornes_http.py` : client HTTP JSON avec URL de base configurable,
  transport injectable pour les tests et pagination via extracteur.
- Décorateur `reessayer_http` : 429, 503, 504, tentatives bornées,
  backoff exponentiel et respect de `Retry-After`.
- `services/etat_reseau.py` : `EtatBorne` normalisé, détection des stations
  vides/pleines, capacités incohérentes, inconnues et sans réponse.
- Collectes `collecter_sequentiel`, `collecter_threads` (1 à 8 workers),
  et `collecter_async` (sémaphore 1 à 8).
- `mesurer_strategies` mesure trois durées ; le résultat réel doit être
  obtenu avec le simulateur officiel dans des conditions identiques.
- Tests sans serveur réel, basés sur des réponses synthétiques et des mocks
  injectés directement dans le transport HTTP.

## Limites importantes — non terminé au regard de l'énoncé

Le fichier **`mobilis-kit/outils/serveur_bornes.py`** n'a pas été
fourni dans le dépôt GitHub, ni dans les pièces visibles lors de ce
développement. Ses **routes, champs de réponse, pagination, scénarios
d'erreur et délai de réponse ne sont donc pas encore vérifiés**.

Par conséquent, il manque encore :

1. Lire le code du simulateur et définir l'extracteur de pages adapté
   au schéma **réel**, sans inventer de route ou champ.
2. Ajouter l'adaptateur qui convertit ses réponses en `EtatBorne`,
   puis brancher la collecte sur toutes les stations.
3. Coupler avec le référentiel validé de **US-01** et son traitement
   des doublons de stations.
4. Mesurer la réponse réelle sur toute la population (objectif < 15 s)
   et comparer séquentiel/threads/asyncio.
5. Brancher la commande finale `mobilis etat` dans l'US-05.
6. Documenter les anomalies API constatées et leurs volumes.

**Nuance de mesure :** `collecter_async` repose aujourd'hui sur
`asyncio.to_thread` (pont entre asyncio et un client HTTP synchrone).
Il ne s'agit **pas** d'un client de socket HTTP asynchrone natif. Le
préciser au jury et le mesurer comme tel ; ne pas le présenter comme
une preuve de supériorité du protocole asyncio.

## Exemples d'utilisation des briques (après mapping serveur)

```python
from mobilis.services.etat_reseau import collecter_threads, comparer_etats

# charger_etat(code_station) est une fonction à écrire en fonction
# des endpoints réels de serveur_bornes.py. Elle retourne EtatBorne.
# etats = collecter_threads(codes_stations, charger_etat, max_simultanes=8)
# rapport = comparer_etats(stations_validees, etats)
```

## Recette à joindre au dossier

- Extraits du simulateur officiel et mapping JSON justifié.
- Exécution des tests `pytest` sans lancer le serveur en CI.
- Commandes, mesures répétées et environnement de benchmark.
- Captures des résultats, cas 429/503/504 et conformité des 8 requêtes.
- Explication du choix technique threads vs asyncio avec limites.
