"""App Flask de monitoring de l'API Trombinoscope.

Routes :
  /            : page d'accueil (présentation de la solution)
  /dashboard   : tableau de bord (dernier run + historique)
  /run         : déclenche une nouvelle exécution des tests (POST anti-spam)
  /runs/<id>   : détail JSON d'un run précis
  /health      : état de santé de la solution
"""
import datetime
import os
import time

from flask import Flask, jsonify, redirect, render_template, request, url_for, flash, session

import storage
from tester.runner import run as run_tests

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-change-me")

MIN_INTERVAL_SECONDS = 30
_last_run_ts = 0.0


try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo(os.getenv("TZ", "Europe/Paris"))
except Exception:
    LOCAL_TZ = datetime.timezone.utc

_FR_MONTHS = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]


def _parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _fmt_timestamp(ts):
    """Format absolu : '14 juin 2026, 17:03'."""
    dt = _parse_ts(ts)
    if not dt:
        return ts or ""
    local = dt.astimezone(LOCAL_TZ)
    return f"{local.day} {_FR_MONTHS[local.month - 1]} {local.year}, {local.strftime('%H:%M')}"


def _fmt_relative(ts):
    """Format relatif : 'il y a 2 min', 'à l'instant', etc."""
    dt = _parse_ts(ts)
    if not dt:
        return ts or ""
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - dt.astimezone(datetime.timezone.utc)
    secs = int(delta.total_seconds())
    if secs < 0:
        return "à l'instant"
    if secs < 10:
        return "à l'instant"
    if secs < 60:
        return f"il y a {secs} s"
    minutes = secs // 60
    if minutes < 60:
        return f"il y a {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"il y a {hours} h"
    days = hours // 24
    if days < 7:
        return f"il y a {days} j"
    return _fmt_timestamp(ts)


app.jinja_env.filters["fmt_ts"] = _fmt_timestamp
app.jinja_env.filters["fmt_rel"] = _fmt_relative


@app.get("/")
def home():
    latest = storage.latest_run()
    runs_count = len(storage.list_runs(limit=1000))
    return render_template("home.html", latest=latest, runs_count=runs_count)


@app.get("/dashboard")
def dashboard():
    runs = storage.list_runs(limit=20)
    latest = storage.latest_run()
    sparkline = [r["latency_avg"] for r in reversed(runs)][-20:]
    avail_spark = [int(r["availability"] * 100) for r in reversed(runs)][-20:]
    return render_template(
        "dashboard.html",
        runs=runs,
        latest=latest,
        sparkline_latency=sparkline,
        sparkline_avail=avail_spark,
    )


@app.post("/run")
def trigger_run():
    """Lance une nouvelle exécution des tests (anti-spam intégré)."""
    global _last_run_ts
    now = time.time()
    elapsed = now - _last_run_ts
    if elapsed < MIN_INTERVAL_SECONDS:
        wait = int(MIN_INTERVAL_SECONDS - elapsed)
        if request.headers.get("Accept", "").startswith("application/json"):
            return jsonify(error="rate_limited", retry_after=wait), 429
        flash(f"Attends encore {wait}s avant de relancer un test.", "warning")
        return redirect(url_for("dashboard"))

    _last_run_ts = now
    result = run_tests()
    storage.save_run(result)

    if request.headers.get("Accept", "").startswith("application/json"):
        return jsonify(result)
    summary = result["summary"]
    flash(
        f"Run terminé : {summary['passed']}/{summary['total']} tests passés, "
        f"disponibilité {int(summary['availability'] * 100)}%.",
        "success",
    )
    return redirect(url_for("dashboard"))


@app.get("/runs/<int:run_id>")
def run_detail(run_id):
    run = storage.get_run(run_id)
    if not run:
        return jsonify(error="not_found"), 404
    return jsonify(run)


@app.get("/health")
def health():
    latest = storage.latest_run()
    return jsonify(
        status="ok",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        latest_run_timestamp=latest["timestamp"] if latest else None,
        latest_run_availability=latest["summary"]["availability"] if latest else None,
    )


if __name__ == "__main__":
    storage.init_db()
    port = int(os.getenv("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=True)
