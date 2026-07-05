import sqlite3
import json
import time
import uuid
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "app_data.db")


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                progreso TEXT,
                resultado TEXT,
                documento TEXT,
                created_at REAL
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_job(documento):
    job_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, status, progreso, resultado, documento, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, "pendiente", json.dumps({"mensaje": "En cola"}), None, documento, time.time())
        )
        conn.commit()
    return job_id


def update_job_progress(job_id, mensaje, actual=None, total=None):
    progreso = {"mensaje": mensaje}
    if actual is not None and total is not None:
        progreso["actual"] = actual
        progreso["total"] = total
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, progreso = ? WHERE job_id = ?",
            ("procesando", json.dumps(progreso), job_id)
        )
        conn.commit()


def complete_job(job_id, resultado):
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, resultado = ?, progreso = ? WHERE job_id = ?",
            ("completado", json.dumps(resultado), json.dumps({"mensaje": "Completado"}), job_id)
        )
        conn.commit()


def fail_job(job_id, error_msg):
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, progreso = ? WHERE job_id = ?",
            ("error", json.dumps({"mensaje": error_msg}), job_id)
        )
        conn.commit()


def get_job(job_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return {
            "job_id": row["job_id"],
            "status": row["status"],
            "progreso": json.loads(row["progreso"]) if row["progreso"] else {},
            "resultado": json.loads(row["resultado"]) if row["resultado"] else None,
            "documento": row["documento"]
        }


init_db()