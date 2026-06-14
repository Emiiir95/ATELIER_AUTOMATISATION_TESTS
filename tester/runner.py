"""Exécute la suite de tests + calcule les métriques QoS."""
import datetime
import os

from . import tests as t
from .client import ApiClient

BASE_URL = os.getenv("TROMBI_API_URL", "https://trombi-backend.onrender.com")


def _percentile(values, p):
    if not values:
        return 0
    values = sorted(values)
    k = int(round((p / 100) * (len(values) - 1)))
    return values[k]


def run():
    """Exécute tous les tests et retourne un dict structuré."""
    # Warmup : réveille le free tier Render avec un timeout long avant la suite.
    # Ne compte pas dans les métriques. Échec silencieux si KO.
    warmup_client = ApiClient(BASE_URL, timeout=60.0)
    warmup_client.get("/health")

    client = ApiClient(BASE_URL)
    results = []

    # 1. Tests sans auth
    results.append(t.test_health_ok(client))
    results.append(t.test_login_failure(client))
    results.append(t.test_classes_requires_auth(client))

    # 2. Login pour récupérer un token
    login_result = t.test_login_success(client)
    results.append(login_result)

    token = None
    if login_result["status"] == "PASS":
        # Re-call login to grab the token (test only validated structure)
        status, body, _, _ = client.post(
            "/api/auth/login",
            json={"email": t.ADMIN_EMAIL, "password": t.ADMIN_PASSWORD},
        )
        if status == 200 and isinstance(body, dict):
            token = body.get("token")

    # 3. Tests authentifiés (si on a un token)
    if token:
        results.append(t.test_classes_list(client, token))
        results.append(t.test_students_list(client, token))
        results.append(t.test_students_search(client, token))
        results.append(t.test_me_endpoint(client, token))
        results.append(t.test_promos_list(client, token))
    else:
        # Si pas de token, on marque les tests dépendants comme FAIL
        for name in ("classes_list", "students_list", "students_search",
                     "me_endpoint", "promos_list"):
            results.append({
                "name": name,
                "status": "FAIL",
                "latency_ms": 0,
                "details": "skipped: no token",
            })

    # 4. Calcul des métriques
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = len(results) - passed
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]

    summary = {
        "passed": passed,
        "failed": failed,
        "total": len(results),
        "error_rate": round(failed / len(results), 3) if results else 0,
        "availability": round(passed / len(results), 3) if results else 0,
        "latency_ms_avg": int(sum(latencies) / len(latencies)) if latencies else 0,
        "latency_ms_p95": _percentile(latencies, 95),
        "latency_ms_max": max(latencies) if latencies else 0,
    }

    return {
        "api": "Trombinoscope",
        "base_url": BASE_URL,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": summary,
        "tests": results,
    }
