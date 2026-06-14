"""Stockage SQLite des runs de tests."""
import json
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "runs.db"))


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS runs (
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
            )
        """)


def save_run(run):
    init_db()
    s = run["summary"]
    with _conn() as c:
        c.execute(
            """INSERT INTO runs
               (timestamp, api, base_url, passed, failed, error_rate, availability,
                latency_avg, latency_p95, latency_max, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run["timestamp"], run["api"], run["base_url"],
                s["passed"], s["failed"], s["error_rate"], s["availability"],
                s["latency_ms_avg"], s["latency_ms_p95"], s["latency_ms_max"],
                json.dumps(run, ensure_ascii=False),
            ),
        )


def list_runs(limit=50):
    init_db()
    with _conn() as c:
        rows = c.execute(
            """SELECT id, timestamp, passed, failed, error_rate, availability,
                      latency_avg, latency_p95, latency_max
               FROM runs ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id):
    init_db()
    with _conn() as c:
        row = c.execute(
            "SELECT payload_json FROM runs WHERE id = ?", (run_id,),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["payload_json"])


def latest_run():
    init_db()
    with _conn() as c:
        row = c.execute(
            "SELECT payload_json FROM runs ORDER BY id DESC LIMIT 1",
        ).fetchone()
    return json.loads(row["payload_json"]) if row else None
