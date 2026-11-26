# US-02 — Trajets : plan d'implémentation

**Issue parente :** [#2](https://github.com/abidiDev/mobilis-python-avance/issues/2)  
**Tâches :** [#12 T-07](https://github.com/abidiDev/mobilis-python-avance/issues/12) et [#13 T-08](https://github.com/abidiDev/mobilis-python-avance/issues/13)  
**État :** cadrage initial ; **aucune fonctionnalité métier implémentée dans cette branche pour le moment**.

## Objectif utilisateur

Lire les trajets bruts d'août à octobre 2026 de manière progressive pour mesurer
la fréquentation, en identifiant les données incorrectes et en limitant la mémoire.

## Développement prévu

1. **T-07 — Lecture normalisée** dans `adapters/trajets_csv.py`
   - Ouvrir le vrai `.csv.gz` en flux, avec un générateur composable.
   - Reconnaître les trois présentations de dates et traiter explicitement
     la question des fuseaux et de l'heure d'hiver.
   - Retourner des objets `Trajet` selon `SourceTrajets.lire(signaler)`,
     si ce contrat est bien intégré et validé dans `main`.
   - Détecter les champs invalides, signaler une `Anomalie`, compter
     chaque correction ou rejet et justifier la décision.
   - Traiter les trajets répétés avec une politique documentée et testée.
     **Ne pas** choisir une déduplication mémoire non bornée sans mesurer
     sa croissance ; vérifier l'exigence « fichier 100 fois plus gros ».

2. **T-08 — Fréquentation** dans `services/frequentation.py`
   - Consommer les `Trajet` sans relire les CSV à l'intérieur du service.
   - Calculer les flux par station (départs et arrivées), périodes matin/soir,
     heures et comparaison semaine/week-end selon conventions documentées.
   - Produire les résultats demandés de façon reproductible.
   - Mesurer avec `tracemalloc`, consigner taille d'entrée, pic mémoire,
     temps d'exécution et limites du protocole expérimental.

3. **Tests et documentation**
   - Tests sur fichiers GZIP minimaux, encodage/colonnes, dates, doublons,
     erreurs, valeurs absentes, frontières horaires et week-end.
   - Ajouter des tests qui démontrent un traitement réellement progressif.
   - Documenter la commande finale `mobilis frequentation` avec l'intégrateur CLI.

## Dépendances et collaboration

- La PR de contrats partagés [#24](https://github.com/abidiDev/mobilis-python-avance/pull/24)
  avait été fusionnée sur une branche d'architecture, mais les fichiers
  `domain/models.py`, `domain/contracts.py` et `domain/anomalies.py`
  n'étaient **pas encore présents dans main** lors du cadrage.
  Vérifier leur intégration avant d'importer `Trajet` ou `SourceTrajets`.
- Les décisions à deux sur les dates, anomalies et doublons relèvent de [#8](https://github.com/abidiDev/mobilis-python-avance/issues/8).
- Le module sera réutilisé par la facturation US-03.
- La CLI finale appartient à l'US-05 ; prévoir une API métier simple et documentée.

## Critères de réception

- [ ] `.csv.gz` lu via des générateurs ; aucun chargement intégral.
- [ ] Trois formats de dates correctement interprétés, cas limites testés.
- [ ] Stratégie de dédoublonnage explicitement justifiée.
- [ ] Agrégations matin/soir et semaine/week-end vérifiées sur des cas simples.
- [ ] Mesures `tracemalloc` et explication de la scalabilité.
- [ ] Journal des anomalies : types, nombres, décisions, justifications.
- [ ] Tests pytest et validations Ruff, mypy strict et CI verts.
- [ ] Résultats chiffrés reproductibles ; documentation et revue du binôme.

**Ne pas fermer #2 ni #12/#13** avant que leurs livrables soient effectivement implémentés et revus.
