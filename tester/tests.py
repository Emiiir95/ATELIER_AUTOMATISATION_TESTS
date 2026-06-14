"""Suite de tests pour l'API Trombinoscope.

Chaque test retourne un dict {name, status, latency_ms, details}.
status ∈ {"PASS", "FAIL"}.
"""

ADMIN_EMAIL = "admin@trombi.fr"
ADMIN_PASSWORD = "Admin123!"


def _result(name, status, latency_ms, details=""):
    return {
        "name": name,
        "status": status,
        "latency_ms": latency_ms,
        "details": details,
    }


# ── Tests fonctionnels (contrat de l'API) ───────────────────────────────

def test_health_ok(client):
    """GET /health doit renvoyer 200 avec status=ok."""
    status, body, latency, err = client.get("/health")
    if err:
        return _result("health_ok", "FAIL", latency, f"network error: {err}")
    if status != 200:
        return _result("health_ok", "FAIL", latency, f"expected 200, got {status}")
    if not isinstance(body, dict) or body.get("status") != "ok":
        return _result("health_ok", "FAIL", latency, f"body invalide: {body}")
    return _result("health_ok", "PASS", latency)


def test_login_success(client):
    """POST /api/auth/login avec admin valide doit renvoyer 200 + token."""
    status, body, latency, err = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if err:
        return _result("login_success", "FAIL", latency, f"network error: {err}")
    if status != 200:
        return _result("login_success", "FAIL", latency, f"expected 200, got {status}")
    if not isinstance(body, dict) or "token" not in body:
        return _result("login_success", "FAIL", latency, "champ token manquant")
    if not body.get("user") or body["user"].get("role") not in ("ADMIN", "TEACHER"):
        return _result("login_success", "FAIL", latency, "champ user.role manquant")
    return _result("login_success", "PASS", latency)


def test_login_failure(client):
    """POST /api/auth/login avec mauvais password doit renvoyer 401."""
    status, body, latency, err = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": "wrong-password"},
    )
    if err:
        return _result("login_failure", "FAIL", latency, f"network error: {err}")
    if status != 401:
        return _result("login_failure", "FAIL", latency, f"expected 401, got {status}")
    return _result("login_failure", "PASS", latency)


def test_classes_requires_auth(client):
    """GET /api/classes sans token doit renvoyer 401."""
    status, body, latency, err = client.get("/api/classes")
    if err:
        return _result("classes_requires_auth", "FAIL", latency, f"network error: {err}")
    if status != 401:
        return _result("classes_requires_auth", "FAIL", latency, f"expected 401, got {status}")
    return _result("classes_requires_auth", "PASS", latency)


def test_classes_list(client, token):
    """GET /api/classes avec token valide doit renvoyer une liste."""
    status, body, latency, err = client.get(
        "/api/classes",
        headers={"Authorization": f"Bearer {token}"},
    )
    if err:
        return _result("classes_list", "FAIL", latency, f"network error: {err}")
    if status != 200:
        return _result("classes_list", "FAIL", latency, f"expected 200, got {status}")
    if not isinstance(body, list):
        return _result("classes_list", "FAIL", latency, "réponse n'est pas une liste")
    return _result("classes_list", "PASS", latency, f"{len(body)} classes")


def test_students_list(client, token):
    """GET /api/students avec token valide doit renvoyer une liste."""
    status, body, latency, err = client.get(
        "/api/students",
        headers={"Authorization": f"Bearer {token}"},
    )
    if err:
        return _result("students_list", "FAIL", latency, f"network error: {err}")
    if status != 200:
        return _result("students_list", "FAIL", latency, f"expected 200, got {status}")
    if not isinstance(body, list):
        return _result("students_list", "FAIL", latency, "réponse n'est pas une liste")
    # Vérification structure d'un élève si la liste n'est pas vide
    if body:
        required = {"id", "firstName", "lastName", "email"}
        missing = required - set(body[0].keys())
        if missing:
            return _result("students_list", "FAIL", latency, f"champs manquants: {missing}")
    return _result("students_list", "PASS", latency, f"{len(body)} élèves")


def test_students_search(client, token):
    """GET /api/students?q=alice doit fonctionner avec un filtre texte."""
    status, body, latency, err = client.get(
        "/api/students",
        params={"q": "alice"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if err:
        return _result("students_search", "FAIL", latency, f"network error: {err}")
    if status != 200:
        return _result("students_search", "FAIL", latency, f"expected 200, got {status}")
    if not isinstance(body, list):
        return _result("students_search", "FAIL", latency, "réponse n'est pas une liste")
    return _result("students_search", "PASS", latency, f"{len(body)} résultats")


def test_me_endpoint(client, token):
    """GET /api/me doit renvoyer le profil de l'utilisateur connecté."""
    status, body, latency, err = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if err:
        return _result("me_endpoint", "FAIL", latency, f"network error: {err}")
    if status != 200:
        return _result("me_endpoint", "FAIL", latency, f"expected 200, got {status}")
    if not isinstance(body, dict) or body.get("email") != ADMIN_EMAIL:
        return _result("me_endpoint", "FAIL", latency, f"email inattendu: {body}")
    return _result("me_endpoint", "PASS", latency)


def test_promos_list(client, token):
    """GET /api/promos doit renvoyer la liste des promotions avec compteurs."""
    status, body, latency, err = client.get(
        "/api/promos",
        headers={"Authorization": f"Bearer {token}"},
    )
    if err:
        return _result("promos_list", "FAIL", latency, f"network error: {err}")
    if status != 200:
        return _result("promos_list", "FAIL", latency, f"expected 200, got {status}")
    if not isinstance(body, list):
        return _result("promos_list", "FAIL", latency, "réponse n'est pas une liste")
    if body:
        required = {"year", "classesCount", "studentsCount"}
        missing = required - set(body[0].keys())
        if missing:
            return _result("promos_list", "FAIL", latency, f"champs manquants: {missing}")
    return _result("promos_list", "PASS", latency, f"{len(body)} promos")
