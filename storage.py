import sqlite3
import json
import time
import uuid
import os
from contextlib import contextmanager


DB_PATH = os.path.join(os.path.dirname(__file__), "app_data.db")
JOB_TTL_SECONDS = 7 * 24 * 60 * 60


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                progreso TEXT,
                resultado TEXT,
                documento TEXT,
                owner_token TEXT,
                created_at REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)")

        cols = [row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()]
        if "owner_token" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN owner_token TEXT")
        conn.commit()


@contextmanager
def get_conn():
    
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        # Activar el modo WAL para permitir lectura y escritura concurrentes sin bloqueos
        conn.execute("PRAGMA journal_mode=WAL;")
        yield conn
    finally:
        conn.close()


def create_job(documento, owner_token):


    job_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, status, progreso, resultado, documento, owner_token, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, "pendiente", json.dumps({"mensaje": "En cola"}), None, documento, owner_token, time.time())
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


def get_job_owner_token(job_id):
    """FIX (seguridad - IDOR): permite a app.py comparar el propietario real
    del job contra el token de sesion del solicitante."""
    with get_conn() as conn:
        row = conn.execute("SELECT owner_token FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return row["owner_token"] if row else None


def purge_old_jobs(max_age_seconds=JOB_TTL_SECONDS):
    cutoff = time.time() - max_age_seconds
    with get_conn() as conn:
        conn.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,))
        conn.commit()


init_db()