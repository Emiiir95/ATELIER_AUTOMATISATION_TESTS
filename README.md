# 🎯 Atelier Testing as Code & API Monitoring — Trombinoscope

Solution de **monitoring automatisé** de l'API du projet [Trombinoscope](https://github.com/Semiiih/Trombinoscope), déployée sur [PythonAnywhere](https://www.pythonanywhere.com/).

L'application Flask exécute périodiquement une suite de **9 tests** sur l'API REST du Trombinoscope (hébergée sur Render), stocke chaque exécution dans une BDD SQLite, et expose un **dashboard** avec les métriques QoS (disponibilité, latence avg/p95/max, taux d'erreur).

---

## 📐 Architecture

```
        [PythonAnywhere]                         [Render]
       ┌───────────────────┐                 ┌──────────────────┐
       │  Flask monitoring │                 │  Trombinoscope   │
       │  (flask_app.py)   │   tests HTTP    │     backend      │
       │                   │ ──────────────▶ │  (Node.js API)   │
       │  /run             │                 │                  │
       │  /dashboard       │ ◀────────────── │  /api/* + /health│
       │  /health          │   réponses      │                  │
       │  /runs/<id>       │                 │                  │
       └─────────┬─────────┘                 └──────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │   SQLite      │
         │   runs.db     │
         │  (historique) │
         └───────────────┘
```

---

## 🗂️ Structure du projet

```
.
├── flask_app.py            # Point d'entrée Flask (routes /run, /dashboard, /health)
├── storage.py              # Persistance SQLite des runs
├── requirements.txt        # Flask + requests
│
├── tester/
│   ├── __init__.py
│   ├── client.py           # Wrapper HTTP : timeout, retry, mesure latence
│   ├── tests.py            # 9 tests sur l'API Trombinoscope
│   └── runner.py           # Orchestration des tests + calcul des métriques
│
├── templates/
│   ├── consignes.html      # Page d'accueil (consignes de l'atelier)
│   └── dashboard.html      # Tableau de bord avec KPIs + historique
│
├── .github/workflows/
│   └── deploy-pythonanywhere.yml  # Déploiement auto sur PythonAnywhere
│
├── API_CHOICE.md           # Fiche descriptive de l'API testée
└── README.md
```

---

## 🧪 Suite de tests (9 tests)

| Nom | Endpoint | Vérifie |
|---|---|---|
| `health_ok` | `GET /health` | Status 200 + body `{"status":"ok"}` |
| `login_success` | `POST /api/auth/login` | Status 200 + token + user.role |
| `login_failure` | `POST /api/auth/login` (mauvais pwd) | Status 401 |
| `classes_requires_auth` | `GET /api/classes` (sans token) | Status 401 |
| `classes_list` | `GET /api/classes` (avec token) | Status 200 + liste |
| `students_list` | `GET /api/students` | Status 200 + structure d'un Student |
| `students_search` | `GET /api/students?q=alice` | Filtre fonctionnel |
| `me_endpoint` | `GET /api/me` | Profil de l'utilisateur connecté |
| `promos_list` | `GET /api/promos` | Liste des promos avec compteurs |

### Catégories de tests

- **Contrat (5)** : codes HTTP, types JSON, champs obligatoires
- **Auth (3)** : login OK, login KO, protection des routes
- **Robustesse (intégrée)** : timeout 5s, 1 retry sur 429/5xx, gestion des erreurs réseau

---

## 📊 Métriques QoS calculées

| Métrique | Description |
|---|---|
| `availability` | % de tests passés sur le dernier run |
| `error_rate` | % de tests échoués |
| `latency_ms_avg` | Latence moyenne en ms |
| `latency_ms_p95` | 95e percentile des latences |
| `latency_ms_max` | Latence maximale observée |

---

## 🚀 Routes Flask

| Route | Méthode | Description |
|---|---|---|
| `/` | GET | Page d'accueil (consignes de l'atelier) |
| `/dashboard` | GET | Tableau de bord (KPIs + historique des 20 derniers runs) |
| `/run` | GET / POST | Déclenche une exécution complète des tests (anti-spam 30s) |
| `/runs/<id>` | GET | Détail JSON d'un run précis |
| `/health` | GET | État de santé de la solution de monitoring elle-même |

---

## 🔧 Installation locale

```bash
# 1. Clone
git clone git@github.com:Emiiir95/ATELIER_AUTOMATISATION_TESTS.git
cd ATELIER_AUTOMATISATION_TESTS

# 2. Virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 3. Dépendances
pip install -r requirements.txt

# 4. Lancement
python flask_app.py
```

Puis ouvrir [http://localhost:5000/dashboard](http://localhost:5000/dashboard) et cliquer **▶️ Lancer un test**.

### Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `TROMBI_API_URL` | `https://trombi-backend.onrender.com` | Cible à tester |
| `DB_PATH` | `./runs.db` | Chemin de la BDD SQLite |

---

## ☁️ Déploiement sur PythonAnywhere

### 1. Créer le webapp

1. Inscription sur [pythonanywhere.com](https://www.pythonanywhere.com/)
2. **Web → Add a new web app → Flask → Python 3.13**
3. Noter le **target dir** (ex: `/home/Emiiir95/mysite`) et le **domaine** (ex: `Emiiir95.pythonanywhere.com`)

### 2. Récupérer un API token

**Account → API Token → Create new** → copier le token

### 3. Configurer les secrets GitHub

Sur ton repo → **Settings → Secrets and variables → Actions → New repository secret** :

| Secret | Valeur |
|---|---|
| `PA_USERNAME` | Ton username PythonAnywhere |
| `PA_TOKEN` | L'API token créé |
| `PA_TARGET_DIR` | `/home/<username>/mysite` |
| `PA_WEBAPP_DOMAIN` | `<username>.pythonanywhere.com` |

### 4. Activer GitHub Actions

Onglet **Actions** → bouton vert "I understand my workflows, go ahead and enable them"

### 5. Trigger le premier déploiement

```bash
git commit -m "trigger deploy" --allow-empty
git push
```

Le workflow `deploy-pythonanywhere.yml` upload tous les fichiers et reload le webapp.

### 6. Planifier les runs automatiques

Sur PythonAnywhere :
1. **Tasks → Add a new scheduled task**
2. Commande : `curl -sS https://<username>.pythonanywhere.com/run >/dev/null`
3. Fréquence : toutes les heures (ou 5 min selon ton compte)

→ Le dashboard se mettra à jour automatiquement sans intervention.

---

## 🛡️ Robustesse

Le client HTTP (`tester/client.py`) gère :

- **Timeout strict** : 5 secondes par requête
- **1 retry maximum** sur :
  - Code 429 (rate limit)
  - Code 5xx (erreur serveur)
  - Exception réseau (timeout, DNS, connexion refusée)
- **Backoff** : 1 seconde entre les 2 tentatives
- **Cold start Render** : si la 1re requête timeout (free tier qui dort), le retry après 1s laisse le serveur démarrer

L'app Flask a un **anti-spam** : 1 run max toutes les 30 secondes (`MIN_INTERVAL_SECONDS`).

---

## 🆘 Troubleshooting

### Tests `login_*` qui FAIL avec network error
Le backend Trombinoscope est probablement endormi (cold start Render). Relance le run, le retry devrait réveiller le serveur.

### Tous les tests authentifiés FAIL
Le login a échoué → vérifier que la BDD Postgres Render est toujours active (le free tier expire au bout de 90 jours).

### Erreur PythonAnywhere "Module not found"
S'assurer que `requirements.txt` est bien dans le target dir et installer manuellement :
```bash
pip3.13 install --user -r requirements.txt
```

### Logs PythonAnywhere
- Access log : `<domain>.pythonanywhere.com.access.log`
- Error log : `<domain>.pythonanywhere.com.error.log`
- Server log : `<domain>.pythonanywhere.com.server.log`

---

## 📚 Checklist atelier (barème /20)

- ✅ Choix API + contrat documenté (`API_CHOICE.md`)
- ✅ Tests implémentés (**9 tests**, requis ≥ 6)
- ✅ Robustesse : timeout + retry, gestion 429/5xx
- ✅ QoS : latence avg/p95/max, taux d'erreur, disponibilité
- ✅ Dashboard accessible (`/dashboard`)
- ✅ Historique en SQLite
- ✅ Endpoint `/health` (bonus)
- ⏳ Déploiement PythonAnywhere
- ⏳ Tâche planifiée

---

## 🔗 Liens

- Repo principal du Trombinoscope : [github.com/Semiiih/Trombinoscope](https://github.com/Semiiih/Trombinoscope)
- API testée : [trombi-backend.onrender.com](https://trombi-backend.onrender.com/health)
- Atelier PRA/PCA (projet sœur) : [github.com/Emiiir95/ATELIER_PRA_PCA](https://github.com/Emiiir95/ATELIER_PRA_PCA)
