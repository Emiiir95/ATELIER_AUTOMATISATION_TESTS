"""App Flask de monitoring de l'API Trombinoscope.

Routes :
  /            → consignes initiales (template fourni par l'atelier)
  /dashboard   → tableau de bord (dernier run + historique)
  /run         → déclenche une nouvelle exécution des tests
  /runs/<id>   → détail JSON d'un run précis
  /health      → état de santé de la solution
"""
import datetime
import time

from flask import Flask, jsonify, redirect, render_template, request, url_for

import storage
from tester.runner import run as run_tests

app = Flask(__name__)

# Anti-spam : 1 run / 30 secondes
MIN_INTERVAL_SECONDS = 30
_last_run_ts = 0.0


@app.get("/")
def consignes():
    return render_template("consignes.html")


@app.get("/dashboard")
def dashboard():
    runs = storage.list_runs(limit=20)
    latest = storage.latest_run()
    return render_template("dashboard.html", runs=runs, latest=latest)


@app.route("/run", methods=["GET", "POST"])
def trigger_run():
    """Lance une nouvelle exécution des tests (anti-spam intégré)."""
    global _last_run_ts
    now = time.time()
    if now - _last_run_ts < MIN_INTERVAL_SECONDS:
        wait = int(MIN_INTERVAL_SECONDS - (now - _last_run_ts))
        if request.method == "GET":
            return redirect(url_for("dashboard"))
        return jsonify(error="rate_limited", retry_after=wait), 429

    _last_run_ts = now
    result = run_tests()
    storage.save_run(result)

    if request.method == "GET":
        return redirect(url_for("dashboard"))
    return jsonify(result)


@app.get("/runs/<int:run_id>")
def run_detail(run_id):
    run = storage.get_run(run_id)
    if not run:
        return jsonify(error="not_found"), 404
    return jsonify(run)


@app.get("/health")
def health():
    """Endpoint de santé de la solution de monitoring elle-même."""
    latest = storage.latest_run()
    return jsonify(
        status="ok",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        latest_run_timestamp=latest["timestamp"] if latest else None,
        latest_run_availability=latest["summary"]["availability"] if latest else None,
    )


if __name__ == "__main__":
    storage.init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
