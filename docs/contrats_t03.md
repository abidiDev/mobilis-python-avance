# T-03 — Contrats de données partagés

> Contrats proposés pour revue par le binôme. Les structures sont implémentées
> dans `src/mobilis/domain/` sur une branche dédiée, mais aucune règle métier
> des cas Stations, Trajets, Facturation ou API n'est encore implémentée.

## Contrats du domaine

| Objet / enum | Fichier | Utilisateurs |
|---|---|---|
| `Station`, `StatutStation` | `domain/models.py` | Lecteur CSV, validation, état du réseau |
| `Trajet`, `TypeVelo` | `domain/models.py` | Lecteur GZIP, fréquentation, facturation |
| `PeriodeAbonnement`, `FormuleAbonnement` | `domain/models.py` | Lecteur JSONL, facturation |
| `TarifFormule`, `GrilleTarifaire`, `ConfigurationTarifaire` | `domain/models.py` | Lecteur JSON, facturation |
| `Anomalie`, `NiveauAnomalie` | `domain/anomalies.py` | Tous les lecteurs et services |

Tous les modèles sont `@dataclass(frozen=True, slots=True)`. Cette immutabilité
évite les modifications accidentelles d'objets partagés ; elle n'implique pas
la validation automatique des attributs à l'exécution. Les champs `Mapping`
dans `GrilleTarifaire` restent à fournir sous une collection non mutable
si l'immutabilité profonde est requise.

### Types transversaux

- Identifiants `str` : station `"MB-0033"`, trajet `"T0000001"`, abonné `"A003495"`, vélo `"V00616"`.
- `date` pour les mises en service et périodes d'abonnement.
- `datetime` **avec fuseau** pour les instants des trajets. UTC en interne ;
  `Europe/Paris` pour les calculs de fréquentation locale (hypothèse sur les
  timestamps français sans fuseau à confirmer).
- `Decimal` pour tous les montants de tarification.
- `None` pour les valeurs véritablement absentes. Un objet incomplet n'est
  pas automatiquement à rejeter ou à facturer différemment.
- `Iterator[Trajet]` : les trajets sont consommés en flux.
- Les trois codes de station répétés ne sont **pas** écrasés par un
  `dict[str, Station]` : la source produit un flux de `Station` ; un service
  décide ensuite comment construire un référentiel exploitable.

## Ports de lecture (interfaces)

Définis dans `domain/contracts.py`, sous forme de `typing.Protocol`.

| Port | Méthode | Retour |
|---|---|---|
| `SourceStations` | `lire(signaler)` | `Iterator[Station]` |
| `SourceTrajets` | `lire(signaler)` | `Iterator[Trajet]` |
| `SourceAbonnements` | `lire(signaler)` | `Iterator[PeriodeAbonnement]` |
| `SourceTarifs` | `lire(signaler)` | `ConfigurationTarifaire` |

Les adapters concrets recevront leurs chemins `Path` lors de leur création,
selon une implémentation à venir. Un adapter peut respecter le protocole sans
hériter d'une classe de base. La CLI orchestre les sources et les services.
Les services métier ne doivent pas importer les adapters.

### Exemple d'utilisation future

```python
from mobilis.domain.anomalies import CollecteurAnomalies

journal = CollecteurAnomalies()
# SourceTrajets est un Protocol : la classe CSV concrète sera livrée en T-07.
trajets = source_trajets.lire(journal.signaler)
# Le service de fréquentation consommera les objets Trajet en T-08.
```

## Contrat commun du journal d'anomalies

`Anomalie` contient les champs :

```text
fichier_source ; ligne ; identifiant ; champ ; code_anomalie ;
niveau ; valeur_observee ; traitement_propose
```

- `ligne` est un numéro physique **à partir de 1** ou `None` lorsqu'il
  n'existe pas de ligne (réponse HTTP, contrôle global).
- `niveau` est `erreur`, `alerte` ou `info` ; ces niveaux sont des
  **conventions du projet** et ne se confondent pas avec un rejet automatique.
- `SignalerAnomalie` est un callback commun : `Callable[[Anomalie], None]`.
- `CollecteurAnomalies` stocke les signalements en mémoire par exécution ;
  un export CSV final pourra être ajouté sans faire dépendre les services
  du format de sérialisation.
- Le journal de l'audit initial inclut une colonne supplémentaire
  `validation_binome` : elle concerne le suivi de revue, pas l'objet métier.
- Les fichiers bruts ne sont jamais modifiés.

## Hors du périmètre de cette branche

La classe `Station` n'assure pas encore la validation du contenu du CSV ;
`Trajet` ne dédoublonne pas ; `ConfigurationTarifaire` ne calcule aucun prix.
Les décisions de calcul restent dans les services. Les ports HTTP, le contrat
complet de tarification `Protocol/ABC` et les rapports finaux seront définis
après vérification des spécifications correspondantes, sans supposer leur API.

## Checklist de revue commune (issue #8)

- [ ] Valider les champs des objets à partir des quatre fichiers.
- [ ] Valider le fuseau des dates sans décalage et les cas d'heure ambiguë.
- [ ] Valider la classification et le format du journal d'anomalies.
- [ ] Valider le traitement des trois codes de stations répétés.
- [ ] Valider la politique de dédoublonnage des 620 trajets répétés.
- [ ] Valider les règles R1–R12 et les interfaces du serveur une fois les deux
      fichiers de spécification disponibles.
- [ ] Revue croisée de la PR et CI verte avant fusion.
