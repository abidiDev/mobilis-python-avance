# US-04 — État temps réel : intégration au simulateur officiel

## Source vérifiée (25/11/2026)

Fichier transmis par le membre du binôme : **`mobilis-kit/outils/serveur_bornes.py`**
(kit PYA-701, serveur HTTP local, non modifié).

Contrat HTTP découvert **dans le code source du simulateur** :

- Adresse : `http://127.0.0.1:8765/`, via `ThreadingHTTPServer`.
- **Authentification** : `X-Api-Key: demo-mobilis-2026` sur chaque GET.
- `GET /stations?page=N` : `{"page": N, "stations": ["MB-0001",...], "page_suivante": N+1|null}`, **25 codes/page**.
- `GET /stations/<code>` : `{"code": "...", "velos_mecaniques": int, "velos_electriques": int, "places_libres": int, "horodatage": "...+00:00"}`.
- Capacité d'appels simultanés : **8**. Au-delà, le serveur retourne **429** et `Retry-After: 1`.
- En mode normal, le serveur est parfois lent, retourne aléatoirement **503**, et certaines stations `hors_ligne` retournent **504**.
- `--calme` désactive les délais, erreurs 503 et états hors-ligne pour déboguer.

**Les routes et champs ci-dessus sont tirés du code officiel, pas des hypothèses.**

## Fonctionnalités codées

- `adapters/bornes_http.py` : client HTTP générique, clé API en en-tête
  (sans casser l'injection de transport des tests), JSON, protection contre
  URL externe, tentatives limitées sur 429/503/504 et prise en compte de
  `Retry-After`.
- `adapters/bornes_mobilis.py` : adaptateur spécialisé qui parcourt
  toutes les pages, valide les codes et les réponses, vérifie l'horodatage
  avec fuseau, normalise **mécaniques + électriques = vélos disponibles**.
- `services/etat_reseau.py` : `EtatBorne`, algorithmes séquentiel,
  ThreadPoolExecutor **max 8**, asyncio avec `to_thread`,
  comparaison avec le référentiel US-01, et collecte résiliente
  `collecter_threads_avec_erreurs` : en cas de HTTP 504 définitif,
  la réponse manquante est signalée sans arrêter les autres.
- `scripts/mesurer_bornes.py` : lance la vraie collecte, affiche
  nombre de bornes, succès/échecs par station, stations vides/pleines,
  totaux mécaniques/électriques, temps de pagination, collecte et total,
  et indique séparément si le temps total est **< 15 s**.
- `tests/test_bornes_mobilis.py` : tests du schéma exact, header API,
  pagination normale/invalide, champs invalides, 401 non réessayé,
  récupération partielle sur 504 et borne de concurrence à 8.
- `tests/test_etat_reseau.py` : retry 429/503/504, Retry-After,
  timeouts/mocks, threads/asyncio et comparaison aux stations de référence.

## Recette réelle à effectuer sur Windows

Depuis la racine du dépôt `mobilis`, ouvrir **deux terminaux**.

### Terminal 1 — démarrer le vrai simulateur

```powershell
.\.venv\Scripts\python.exe "..\mobilis-kit\outils\serveur_bornes.py"
```

Si le simulateur officiel a été enregistré ailleurs,
adapter uniquement le **chemin du fichier**, sans le modifier.
Conserver ce terminal ouvert.

### Terminal 2 — exécuter la collecte réelle

```powershell
git switch feature/4-etat-temps-reel
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts/mesurer_bornes.py
```

La commande affiche un **JSON** contenant `duree_totale_secondes`
et `objectif_moins_15_secondes`, ainsi que `stations_en_erreur`
et `erreurs_par_station`. En mode normal, le nombre d'échecs
et le délai peuvent varier : le simulateur inclut volontairement des
lenteurs et des erreurs aléatoires.

### Comparaison des trois stratégies (mode calme)

Arrêter le premier serveur avec Ctrl+C puis lancer :

```powershell
.\.venv\Scripts\python.exe "..\mobilis-kit\outils\serveur_bornes.py" --calme
```

Dans le second terminal :

```powershell
.\.venv\Scripts\python.exe scripts/mesurer_bornes.py --comparer-strategies
```

La comparaison se fait sur les mêmes **codes** et la même machine,
mais le simulateur peut faire légèrement varier les stocks entre
les consultations ; l'ordre des expériences peut aussi influer.

**Attention** : `asyncio.to_thread` n'est pas un vrai client HTTP
asynchrone natif ; c'est une orchestration asyncio de threads.

## État de la réception

- [x] Contrat exact du simulateur inspecté et intégré.
- [x] Authentification et schéma JSON prévus et testés avec des mocks.
- [x] Décorateur de retry 429/503/504 et Retry-After testé.
- [x] Limite **8** contrôlée dans des tests de concurrence.
- [x] Les erreurs individuelles n'interrompent pas toute la collecte.
- [x] Première exécution **contre le véritable serveur officiel** depuis
      le poste Windows du membre, sortie JSON ci-dessous.
- [x] Une exécution avec **temps total < 15 s** (10,142 s) mesurée ;
      **146/149 réponses**, 3 bornes en 504 : cette mesure valide le seuil
      pour ce passage, pas une garantie sur chaque exécution aléatoire.
- [x] Comparaison des trois stratégies sur le serveur officiel (mode calme),
      une exécution documentée ci-dessous.
- [ ] Rapprochement avec les **vraies stations validées d'US-01**, en
      distinguant les absences du référentiel et les échecs HTTP.
- [ ] Intégration avec la CLI installée `mobilis etat` (ticket US-05).
- [ ] Revue du binôme et fusion PR #27.

La PR reste **draft** jusqu'à la recette avec le vrai serveur et la
validation du binôme. Les tests unitaires sans serveur et le serveur
réel constituent deux niveaux de preuves différents.

## Première recette contre le simulateur officiel — 25/11/2026

Exécution du script `scripts/mesurer_bornes.py` sous Windows,
**serveur du kit en mode normal**. Résultats reproduits de la sortie
du terminal transmise par l'utilisateur :

| Mesure | Résultat observé |
|---|---:|
| Codes de station listés | **149** |
| États reçus et normalisés | **146** |
| Bornes sans réponse finale | **3** |
| Stations vides | **MB-0097** |
| Stations pleines | **0** |
| Vélos mécaniques disponibles | **807** |
| Vélos électriques disponibles | **829** |
| Total vélos disponibles | **1 636** (=807+829) |
| Places libres | **2 232** |
| Durée pagination | **1,627 s** |
| Durée collecte | **8,515 s** |
| Durée totale | **10,142 s** |
| Limite de concurrence configurée | **8** |
| Critère de durée < 15 s | **Atteint sur cette exécution** |
| Collecte complète (149/149) | **Non** |

Bornes indisponibles (erreur finale **HTTP 504 Gateway Timeout**) :
`MB-0079`, `MB-0100`, `MB-0150`.

### Interprétation

La collecte a bien parcouru toutes les pages, puis traité les 149 codes.
Elle a conservé les **146 réussites** malgré les **3 erreurs individuelles**,
sans inventer de valeurs pour les bornes injoignables.
Sur ce passage, l'API a répondu en moins de 15 secondes. Le simulateur
comporte toutefois de l'aléatoire : **une seule exécution ne prouve pas
une borne supérieure de 15 secondes pour tous les passages**.

Le nombre de bornes du serveur n'est **pas nécessairement égal** au
nombre de stations du CSV de référence ; le rapprochement entre
les deux sources dépend du référentiel validé dans US-01.

### Travail restant dans la PR

- Comparatif séquentiel / threads / asyncio.to_thread sur le serveur officiel
  avec `--calme` : **première mesure archivée ci-dessous**.
- Comparaison aux capacités et identifiants du vrai CSV issu de US-01.
- Commande finale `mobilis etat` prévue avec US-05.
- Revue du binôme avant fusion.

## Recette comparative en mode calme — 25/11/2026

Second passage effectué sur le vrai `serveur_bornes.py --calme` avec
`scripts/mesurer_bornes.py --comparer-strategies` sous Windows.
Les valeurs ci-dessous proviennent de la sortie du terminal
transmise par l'utilisateur (fin du JSON ; les premiers champs de cette
sortie n'ont pas été recopiés).

| Indicateur | Résultat observé |
|---|---:|
| Erreurs par station | **Aucune** (`{}`) |
| Erreurs par type | **Aucune** (`{}`) |
| Collecte complète | **Oui** |
| Places libres totales | **2 270** |
| Pagination | **0,096 s** |
| Collecte principale | **0,732 s** |
| Total de la collecte principale | **0,829 s** |
| Limite de concurrence | **8** |
| Seuil de 15 secondes | **Atteint** |

### Comparaison des trois stratégies (une exécution chacune)

| Méthode | Durée mesurée |
|---|---:|
| Séquentielle | **0,529 s** |
| `ThreadPoolExecutor` (8 maximum) | **0,562 s** |
| `asyncio.to_thread` (sémaphore 8) | **0,229 s** |

Sur **cette exécution particulière**, l'approche `asyncio.to_thread`
est la plus rapide. Il ne faut pas généraliser ce classement à partir
d'une unique mesure : en mode calme le serveur ne simule plus la lenteur
réseau, et les écarts très courts sont sensibles au bruit de mesure,
à l'ordonnancement et à l'état du serveur. `asyncio.to_thread`
s'appuie lui aussi sur des threads et n'est **pas un transport HTTP
asynchrone natif**. Les passages sont successifs et les stocks peuvent
légèrement évoluer.

**Bilan US-04 :** le schéma HTTP officiel, le retry, la collecte bornée
à 8, la tolérance aux erreurs et les mesures en mode normal et calme
sont documentés. Les dépendances transverses restantes sont
le rapprochement avec le référentiel validé (US-01),
la commande installée `mobilis etat` (US-05)
et la revue de code du binôme avant fusion.
