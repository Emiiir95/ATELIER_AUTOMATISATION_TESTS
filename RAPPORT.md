# Rapport — Atelier "Testing as Code & API Monitoring"

> Document de synthèse à utiliser comme base de rédaction et support oral.
> Auteur : Emir Sen — B3 — ESIEE-IT

---

## 1. Contexte de l'atelier

### 1.1 Énoncé

L'objectif de cet atelier est de **passer du rôle de développeur à celui d'ingénieur qualité**. Il s'agit de :

1. Choisir une API publique
2. Concevoir et implémenter une solution **automatisée de tests**
3. Déployer la solution sur PythonAnywhere via GitHub Actions
4. Mesurer et exposer des **indicateurs de qualité de service** (QoS)

L'atelier insiste sur les notions de **"testing as code"** (les tests sont versionnés dans le repo, lisibles, exécutables à la demande) et de **monitoring d'API** (mesurer dans le temps la disponibilité, la latence, le taux d'erreur).

### 1.2 Originalité du projet

Plutôt que de tester une API publique aléatoire (Agify, IPify, etc.), j'ai choisi de tester **ma propre API** : le backend du projet **Trombinoscope** déployé sur Render.com (`https://trombi-backend.onrender.com`).

Cela apporte plusieurs avantages pédagogiques :
- Boucle complète projet → tests sur mon propre projet
- API plus riche que les exemples (authentification JWT, filtres, plusieurs ressources)
- Cas réaliste d'un environnement de **prod free tier** avec ses limites (cold start, latence variable)

---

## 2. Vue d'ensemble de la solution

### 2.1 Architecture

```
        [PythonAnywhere — Plan Developer]                 [Render.com]
       ┌──────────────────────────────┐                 ┌──────────────────┐
       │  Flask monitoring app        │   HTTP tests    │  Trombinoscope   │
       │  (flask_app.py)              │ ──────────────▶ │     backend      │
       │                              │                 │   (Node.js)      │
       │  Routes :                    │                 │                  │
       │   - /          Overview      │ ◀────────────── │  /api/* /health  │
       │   - /dashboard Tableau bord  │   réponses      │                  │
       │   - /run       Trigger run   │                 │                  │
       │   - /runs/<id> Détail JSON   │                 └──────────────────┘
       │   - /health    État          │
       └───────────────┬──────────────┘
                       │
                       ▼
              ┌──────────────────┐                 ┌────────────────────┐
              │  SQLite          │                 │  GitHub Actions    │
              │  (runs.db)       │                 │  Auto-deploy sur   │
              │  Historique      │                 │  push main         │
              └──────────────────┘                 └────────────────────┘
```

### 2.2 Composants principaux

| Composant | Fichier | Rôle |
|---|---|---|
| App Flask | `flask_app.py` | Point d'entrée, gère les 5 routes web et l'anti-spam |
| Client HTTP | `tester/client.py` | Wrapper autour de `requests` : timeout, retry, mesure latence |
| Tests | `tester/tests.py` | 9 tests fonctionnels sur l'API Trombinoscope |
| Runner | `tester/runner.py` | Orchestre les tests + calcule les métriques QoS |
| Storage | `storage.py` | Persistance SQLite des runs (historique) |
| Dashboard | `templates/dashboard.html` | Vue web des résultats |
| Page d'accueil | `templates/home.html` | Présentation de la solution |
| Layout commun | `templates/base.html` | Navigation, styles, flash messages |
| Workflow CI | `.github/workflows/deploy-pythonanywhere.yml` | Déploiement automatique |

---

## 3. La suite de tests (9 tests)

### 3.1 Liste exhaustive

| # | Nom du test | Endpoint | Vérifie |
|---|---|---|---|
| 1 | `health_ok` | `GET /health` | Statut 200, body `{"status":"ok"}` |
| 2 | `login_success` | `POST /api/auth/login` | Statut 200, présence du token JWT, role admin |
| 3 | `login_failure` | `POST /api/auth/login` (mauvais pwd) | Statut 401 (rejet correct) |
| 4 | `classes_requires_auth` | `GET /api/classes` (sans token) | Statut 401 (protection active) |
| 5 | `classes_list` | `GET /api/classes` (avec token) | Statut 200, liste valide |
| 6 | `students_list` | `GET /api/students` | Statut 200, structure d'un Student conforme |
| 7 | `students_search` | `GET /api/students?q=alice` | Filtre textuel fonctionne |
| 8 | `me_endpoint` | `GET /api/me` | Profil utilisateur cohérent (email = admin) |
| 9 | `promos_list` | `GET /api/promos` | Liste promos avec compteurs |

L'atelier exigeait **≥ 6 tests** : j'en ai implémenté **9** pour couvrir plus largement le contrat de l'API.

### 3.2 Catégories de tests

| Catégorie | Tests | Objectif |
|---|---|---|
| **Contrat** (5 tests) | health_ok, classes_list, students_list, me_endpoint, promos_list | Vérifier que l'API respecte son contrat (codes HTTP, structure JSON, champs) |
| **Auth** (3 tests) | login_success, login_failure, classes_requires_auth | Vérifier la sécurité (login OK/KO, protection des routes) |
| **Recherche** (1 test) | students_search | Vérifier les fonctionnalités métier (filtre textuel) |

### 3.3 Convention de retour

Chaque test retourne un dictionnaire structuré :

```python
{
    "name": "health_ok",
    "status": "PASS" | "FAIL",
    "latency_ms": 122,
    "details": "3 classes"  # optionnel, message contextuel
}
```

Cela permet au runner de :
- Compter les passés / échoués
- Calculer les statistiques de latence
- Afficher les détails dans le dashboard

---

## 4. Robustesse du client HTTP

Le fichier [`tester/client.py`](tester/client.py) implémente un wrapper minimaliste autour de `requests` avec **3 mécanismes de robustesse** :

### 4.1 Timeout strict

Toutes les requêtes ont un **timeout de 5 secondes** par défaut. Au-delà, on considère l'appel comme un échec réseau.

### 4.2 Retry sur erreurs transitoires

Si la requête retourne :
- Code **429** (rate limit)
- Code **5xx** (erreur serveur)
- Lève une **exception réseau** (timeout, DNS, connexion refusée)

Alors on attend **1 seconde** et on **réessaie une fois**. Si le 2e essai échoue, on remonte l'erreur.

### 4.3 Mesure de latence

Avant chaque requête, on mémorise `time.perf_counter()`. Après réception, on calcule `(t1 - t0) * 1000` en millisecondes.

### 4.4 Warmup spécifique au free tier Render

Le backend Trombinoscope tourne sur Render free tier qui **s'endort après 15 minutes d'inactivité**. La première requête peut prendre 30-50 secondes pour réveiller le serveur.

Pour éviter de polluer les métriques avec ce cold start, le runner effectue un **appel de warmup** (`GET /health` avec timeout 60 s) AVANT de lancer la suite de tests. Ce warmup ne compte pas dans les métriques.

```python
def run():
    # Warmup : timeout long, hors métriques
    warmup_client = ApiClient(BASE_URL, timeout=60.0)
    warmup_client.get("/health")

    # Suite normale : timeout strict 5s
    client = ApiClient(BASE_URL)
    ...
```

---

## 5. Métriques QoS

### 5.1 Calculées par le runner

| Métrique | Formule | Sens |
|---|---|---|
| `passed` / `failed` | Comptage simple | Nombre de tests OK / KO |
| `availability` | `passed / total` | Disponibilité du service (de 0 à 1) |
| `error_rate` | `failed / total` | Taux d'erreur (de 0 à 1) |
| `latency_ms_avg` | moyenne des latences | Latence moyenne |
| `latency_ms_p95` | 95e percentile | Latence "haute" — exclut les outliers |
| `latency_ms_max` | maximum | Pire cas observé |

### 5.2 Interprétation

| Disponibilité | Statut visuel | Sens |
|---|---|---|
| ≥ 95 % | Vert (OK) | Service en bonne santé |
| 70-94 % | Jaune (warning) | Dégradation, à surveiller |
| < 70 % | Rouge (danger) | Service en panne |

Le **p95** est plus représentatif que la moyenne car il filtre les outliers (ex: 1 requête à 5 s qui fausse une moyenne sinon basse).

---

## 6. L'application Flask

### 6.1 Routes

| Route | Méthode | Description |
|---|---|---|
| `/` | GET | Page d'accueil (présentation de la solution) |
| `/dashboard` | GET | Tableau de bord avec KPIs et historique |
| `/run` | POST | Déclenche un nouveau run (anti-spam 30 s) |
| `/runs/<id>` | GET | Détail JSON d'un run précis |
| `/health` | GET | État de santé de la solution elle-même |

### 6.2 Anti-spam

Variable globale `_last_run_ts` qui mémorise le timestamp du dernier run. Si on essaie de relancer avant 30 secondes, on affiche un flash message "Attends encore Xs avant de relancer un test".

Cela évite :
- Le spam involontaire en cliquant plusieurs fois
- La surcharge de l'API Trombinoscope cible
- Le dépassement du quota CPU PythonAnywhere

### 6.3 Filtres de templates

Deux filtres Jinja personnalisés pour formater les timestamps :

- `fmt_ts` : "14 juin 2026, 17:03" (absolu, en heure locale Europe/Paris)
- `fmt_rel` : "à l'instant", "il y a 5 min", "il y a 2 h", etc.

Le dashboard utilise le relatif pour la lisibilité, avec l'absolu disponible au survol (`title` attribut).

---

## 7. Persistance SQLite

Le fichier [`storage.py`](storage.py) gère une base SQLite (`runs.db`) avec une seule table `runs` :

```sql
CREATE TABLE runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL,
    api           TEXT NOT NULL,
    base_url      TEXT NOT NULL,
    passed        INTEGER NOT NULL,
    failed        INTEGER NOT NULL,
    error_rate    REAL NOT NULL,
    availability  REAL NOT NULL,
    latency_avg   INTEGER NOT NULL,
    latency_p95   INTEGER NOT NULL,
    latency_max   INTEGER NOT NULL,
    payload_json  TEXT NOT NULL
);
```

Pour chaque run, on stocke à la fois les colonnes "indexées" (pour les listings rapides) ET le JSON complet (`payload_json`) qui contient le détail des 9 tests.

Cela permet :
- Listing rapide via `list_runs()` (utilisé par le dashboard)
- Récupération du détail d'un run via `get_run(id)` (utilisé par `/runs/<id>`)
- Historique persistant entre les redémarrages

---

## 8. UI/UX

### 8.1 Choix de design

- **Thème dark minimal** : palette noire avec accents typographiques
- **Typographie** : Inter (interface) + JetBrains Mono (code/data) chargées depuis rsms.me
- **Aucun emoji** : remplacés par des points colorés (status) et badges typographiés (`PASS`/`FAIL`)
- **Sparkline SVG** : mini-graphique de tendance de latence généré côté serveur en Jinja
- **Navigation sticky** : barre du haut avec Overview / Dashboard / Health / GitHub

### 8.2 Cohérence visuelle

Une **base.html** partagée par les 2 pages (Overview et Dashboard) garantit :
- Mêmes couleurs, mêmes espacements
- Mêmes composants (cards, KPIs, tables)
- Réactif (mobile-friendly)

### 8.3 Feedback utilisateur

- Bouton **"Lancer un test"** affiche un flash message après chaque run
- Pendant anti-spam : flash warning indique le temps restant
- Statut visuel immédiat par couleur (vert/jaune/rouge)

---

## 9. Déploiement

### 9.1 GitHub Actions

Le workflow [`.github/workflows/deploy-pythonanywhere.yml`](.github/workflows/deploy-pythonanywhere.yml) est déclenché à chaque push sur `main`. Il :

1. Récupère le code du repo
2. Valide la présence des 4 secrets requis
3. Upload **tous** les fichiers (sauf `.git`, `.venv`, `__pycache__`, `.pyc`) vers PythonAnywhere via leur API REST
4. Reload la webapp via l'API PA

Cela permet le **déploiement continu** : je push, et 30 secondes plus tard la prod est à jour.

### 9.2 Secrets GitHub

| Secret | Rôle |
|---|---|
| `PA_USERNAME` | Mon username PythonAnywhere (`emirTrombi`) |
| `PA_TOKEN` | Token API PythonAnywhere |
| `PA_TARGET_DIR` | Répertoire cible sur PA (`/home/emirTrombi/mysite`) |
| `PA_WEBAPP_DOMAIN` | Domaine de la webapp (`emirTrombi.pythonanywhere.com`) |

### 9.3 PythonAnywhere — plan Developer

J'ai dû passer du **plan Beginner (gratuit)** au **plan Developer ($10/mois)** car :

- Le free tier PythonAnywhere bloque l'accès Internet sortant aux domaines non whitelistés
- `trombi-backend.onrender.com` n'est pas dans la whitelist
- Les 4 premiers runs ont tous retourné `Tunnel connection failed: 403 Forbidden`

Avec le plan Developer, l'accès Internet sortant est **illimité** → tous les tests passent.

> Pour le rapport, c'est intéressant à mentionner : la solution a **détecté correctement** l'indisponibilité réseau et l'a rapportée (100 % d'erreur, latence quasi nulle = rejet immédiat par le proxy). Cela démontre la valeur du monitoring même dans un environnement contraint.

### 9.4 Scheduled Task

Sur PythonAnywhere, onglet **Tasks** :

| Champ | Valeur |
|---|---|
| Fréquence | Hourly |
| Heure | `:00` |
| Commande | `curl -sS -X POST https://emirTrombi.pythonanywhere.com/run -o /dev/null` |

→ Chaque heure, un run est lancé automatiquement et persisté en BDD. Le dashboard se met à jour sans intervention.

---

## 10. Mon vécu (résultats réels)

### 10.1 Phases de tests observées

| Run # | Contexte | Résultat |
|---|---|---|
| #1 à #4 | Compte free tier PythonAnywhere | **0 / 9 PASS**, taux d'erreur 100 %, latence 1-3 ms (= rejet par le proxy) |
| #5 | Après upgrade Developer + reload webapp | **9 / 9 PASS**, disponibilité 100 %, latence avg **297 ms**, p95 **891 ms** |

Cette transition est très visible dans le tableau d'historique du dashboard.

### 10.2 Analyse des latences au run #5

| Test | Latence | Interprétation |
|---|---|---|
| `health_ok` | 122 ms | Endpoint simple, juste un dict en retour |
| `login_failure` | 891 ms | **bcrypt.compare** côté serveur = lent intentionnellement (sécurité) |
| `classes_requires_auth` | 108 ms | Rejet immédiat par le middleware d'auth |
| `login_success` | 695 ms | Idem login_failure, ralenti par bcrypt |
| `classes_list` | 118 ms | Requête BDD simple |
| `students_list` | 123 ms | Requête + jointure avec Class |
| `students_search` | 303 ms | Filtre `ILIKE` Postgres, plus lent |
| `me_endpoint` | 203 ms | Décodage JWT + lecture user |
| `promos_list` | 111 ms | Agrégation côté Node.js |

**Observation clé** : les 2 endpoints les plus lents (`login_*`) le sont **par design** (bcrypt). C'est un signal QoS important : si on voulait optimiser, c'est sur ces 2 endpoints qu'il faudrait agir.

### 10.3 Comparaison avec les autres runs

L'historique permet de comparer plusieurs runs et d'observer des **tendances** :
- Le p95 reste autour de 900 ms (cohérent avec bcrypt)
- La latence moyenne varie entre 150 ms et 350 ms selon le temps de réveil de Render
- Aucune dégradation prolongée détectée

---

## 11. Choix techniques justifiés

| Choix | Justification |
|---|---|
| Tester son propre projet | Cohérence pédagogique avec le module global, API plus riche |
| Flask au lieu de FastAPI | Imposé par l'atelier + simplicité |
| SQLite au lieu de PostgreSQL | Pas besoin de DB serveur, fichier portable |
| Tests procéduraux au lieu de pytest | Plus simple à intégrer dans un endpoint Flask, contrôle total |
| Inter + JetBrains Mono | Look professionnel, lisibilité excellente |
| Pas de framework JS | Sparkline en SVG pur, dashboard 100 % server-rendered, plus léger |
| Anti-spam 30 s | Respect du rate-limit du free tier Render |
| Warmup Render | Évite que le cold start pollue les métriques |

---

## 12. Limites et améliorations possibles

| Limite | Impact | Solution prod |
|---|---|---|
| SQLite local au pod PA | Si PA recrée le filesystem, perte d'historique | Migration vers PostgreSQL externe |
| Pas de chiffrement des credentials seed | Email/password d'admin en clair dans le code des tests | Variables d'environnement / Secrets |
| 1 seule cible | On ne teste qu'une API | Multi-cibles via config JSON |
| Pas d'alerting | Une chute de disponibilité n'envoie aucune notif | Webhook Slack / Discord sur seuil |
| Tests synchrones | 9 tests = 9 appels séquentiels | Parallélisation pour mesurer un vrai burst |
| Anti-spam basique | Variable globale, pas thread-safe | Redis ou table SQLite avec lock |

---

## 13. Compétences mises en œuvre

| Compétence | Où dans le projet |
|---|---|
| Conception d'API testée | Tests dans `tester/tests.py` |
| Robustesse HTTP | Timeout + retry dans `client.py` |
| Calcul de métriques QoS | Avg / p95 / availability dans `runner.py` |
| Persistance SQL | `storage.py` avec init_db et requêtes |
| Templating Jinja2 | Filtres personnalisés, héritage `base.html` |
| Design UI/UX | Palette dark minimal, sparkline SVG |
| CI/CD GitHub Actions | Workflow auto-deploy |
| Déploiement cloud | PythonAnywhere + scheduled task |
| Documentation | README + API_CHOICE + RAPPORT |

---

## 14. Checklist du barème (sur 20 points)

| Critère | Pondération | Statut |
|---|---|---|
| Choix API + contrat documenté | 2 pts | ✅ `API_CHOICE.md` rempli |
| Qualité des tests (≥ 6) | 6 pts | ✅ **9 tests** implémentés |
| Robustesse (timeout, retry, 429/5xx) | 4 pts | ✅ implémentés dans `client.py` |
| QoS (latence, taux erreur, interprétation) | 4 pts | ✅ avg/p95/max + dashboard |
| Restitution (dashboard, historique, dernier run) | 4 pts | ✅ dashboard + historique 20 runs |
| **Bonus** : planification stable | +1 | ✅ Scheduled Task hourly |
| **Bonus** : `/health` endpoint | +1 | ✅ implémenté |

**Total estimé : 20 / 20 + bonus** 🎯

---

## 15. Discours pour l'oral (5-7 minutes)

### Introduction (~1 min)

> "L'atelier consistait à automatiser des tests sur une API et exposer des métriques QoS. Plutôt que de tester une API publique aléatoire, j'ai testé mon propre projet Trombinoscope déployé sur Render — ce qui m'a permis de boucler la boucle avec mon B3."

### Architecture (~1 min)

> "La solution est une app Flask qui tourne sur PythonAnywhere. Elle exécute 9 tests sur l'API Trombinoscope, persiste les résultats en SQLite, et expose un dashboard avec les KPIs."

### Tests (~2 min)

> "J'ai 9 tests dans 3 catégories : contrat (codes HTTP, structure JSON), auth (login OK/KO, protection des routes), et fonctionnalités (recherche). Le client HTTP intègre un timeout strict de 5 secondes et un retry sur 429/5xx. J'ai aussi ajouté un warmup pour gérer le cold start du free tier Render."

### Métriques (~1 min)

> "Je calcule la disponibilité, le taux d'erreur, et 3 indicateurs de latence : moyenne, p95 et max. Le p95 est plus pertinent que la moyenne car il filtre les outliers."

### Déploiement (~1 min)

> "Le déploiement est automatisé : à chaque push GitHub, un workflow Actions upload les fichiers via l'API PythonAnywhere et reload la webapp. J'ai aussi configuré une scheduled task qui lance un run chaque heure."

### Démo (~1 min)

> "Voici le dashboard avec les 9 tests verts au dernier run. L'historique montre clairement la transition entre les runs en erreur (avant l'upgrade PythonAnywhere) et ceux à 100 % de disponibilité."

### Conclusion (~30 s)

> "Cette solution est un mini SaaS de monitoring : on pourrait facilement la généraliser pour superviser plusieurs APIs en parallèle, avec alerting Slack en cas de chute de disponibilité."

---

## 16. Glossaire

| Terme | Définition |
|---|---|
| **QoS** | Quality of Service — qualité de service mesurable d'une API |
| **Testing as Code** | Tests versionnés dans le repo Git, exécutables à la demande |
| **Latence p95** | 95e percentile : 95 % des requêtes sont plus rapides que cette valeur |
| **Cold start** | Démarrage à froid : 1re requête lente car le serveur dormait |
| **Whitelist PA** | Liste blanche des domaines accessibles depuis le free tier PythonAnywhere |
| **Sparkline** | Mini-graphique de tendance sans axes, intégré dans une cellule |
| **Anti-spam** | Mécanisme limitant la fréquence d'exécution d'une action |
| **Scheduled Task** | Tâche planifiée (cron-like) côté PythonAnywhere |
| **Warmup** | Appel préalable destiné à "réveiller" un service endormi |
| **Workflow CI** | Pipeline d'intégration continue (ici GitHub Actions) |

---

## 17. Liens utiles

- **App déployée** : https://emirTrombi.pythonanywhere.com
- **Repo GitHub** : https://github.com/Emiiir95/ATELIER_AUTOMATISATION_TESTS
- **API testée** : https://trombi-backend.onrender.com/health
- **Projet principal Trombinoscope** : https://github.com/Semiiih/Trombinoscope
- **Repo atelier PRA/PCA (sœur)** : https://github.com/Emiiir95/ATELIER_PRA_PCA
- **Doc PythonAnywhere whitelist** : https://www.pythonanywhere.com/whitelist/
