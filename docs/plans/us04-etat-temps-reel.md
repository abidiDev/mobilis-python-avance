# US-04 — État temps réel : plan d'implémentation

**Issue parente :** [#4](https://github.com/abidiDev/mobilis-python-avance/issues/4)  
**Tâches :** [#17 T-12](https://github.com/abidiDev/mobilis-python-avance/issues/17) et [#18 T-13](https://github.com/abidiDev/mobilis-python-avance/issues/18)  
**État :** cadrage initial ; **aucune fonctionnalité métier implémentée dans cette branche pour le moment**.

## Objectif utilisateur

Photographier l'état des stations depuis le serveur de bornes simulé, identifier
les stations vides ou pleines et les écarts avec le référentiel local, tout
en maîtrisant le temps de réponse et les appels concurrents.

## Développement prévu

1. **T-12 — Client HTTP et robustesse** dans `adapters/bornes_http.py`
   - Lire `outils/serveur_bornes.py` et ses routes réelles avant d'écrire
     le client (URL, pagination, formats de réponses, erreurs).
   - Construire un client sortant HTTP ; Mobilis **n'héberge pas** une API REST.
   - Implémenter un décorateur de retry réutilisable pour les réponses
     503, 504 et 429, en respectant `Retry-After` et en bornant les essais.
   - Distinguer erreurs transitoires, non transitoires et données invalides.
   - Utiliser des mocks dans les tests, sans serveur réel dans la CI.

2. **T-13 — Concurrence, rapprochement, mesures**
   - Photographier toutes les stations avec **au plus huit appels simultanés**.
   - Comparer les solutions séquentielle, `ThreadPoolExecutor` et `asyncio`
     sur des conditions identiques ; justifier celle retenue.
   - Démontrer un temps total inférieur à 15 secondes **dans les conditions
     prévues par le sujet**, en consignant la commande et les mesures.
   - Rapprocher l'état externe du référentiel de stations validé par US-01
     et signaler les écarts, stations vides/pleines et erreurs de collecte.
   - Isoler les règles de comparaison dans `services/etat_reseau.py`.

3. **Tests et documentation**
   - Mocks couvrant 200, 429 avec `Retry-After`, 503, 504, délais, pagination,
     échec définitif et récupération.
   - Vérifier la borne de concurrence, les comparaisons et les erreurs.
   - Conserver les mesures reproductibles et leurs limites méthodologiques.
   - Préparer l'appel depuis `mobilis etat` via la CLI de US-05.

## Dépendances et collaboration

- Le service de comparaison dépend des stations exploitables de US-01 :
  [#9](https://github.com/abidiDev/mobilis-python-avance/issues/9),
  [#10](https://github.com/abidiDev/mobilis-python-avance/issues/10),
  [#11](https://github.com/abidiDev/mobilis-python-avance/issues/11).
  Le client HTTP et ses mocks peuvent progresser sans attendre ce module.
- Vérifier l'intégration réelle des modèles et du mécanisme d'anomalies
  de la PR [#24](https://github.com/abidiDev/mobilis-python-avance/pull/24)
  dans `main` avant les imports partagés.
- La CLI finale relève de US-05 et utilisera les sorties de ce cas.

## Critères de réception

- [ ] Contrat HTTP conforme au vrai simulateur (pagination incluse).
- [ ] Décorateur retry testé pour 503/504/429 et `Retry-After`.
- [ ] Jusqu'à 8 appels simultanés, maximum vérifié automatiquement.
- [ ] Benchmark séquentiel/threads/asyncio reproductible et argumenté.
- [ ] Temps de la collecte inférieur à 15 s, preuve mesurée.
- [ ] Comparaison avec le référentiel validé, anomalies signalées.
- [ ] Pytest avec mocks, Ruff, mypy strict et CI verts.
- [ ] Résultats, limites et choix documentés ; revue du binôme.

**Ne pas fermer #4 ni #17/#18** avant leurs implémentations et vérifications.
