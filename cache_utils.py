import os
import time
import hashlib
import json
import tempfile
import logging

logger = logging.getLogger("plagiarism_checker")

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache_scraped")
os.makedirs(CACHE_DIR, exist_ok=True)
DEFAULT_TTL = 60 * 60 * 24  # 24 horas
FAILED_TTL = 60 * 30  # 30 minutos para entradas "known-bad"


def _cache_path(key):
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")


def cache_get(key):
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if time.time() - payload["ts"] > payload.get("ttl", DEFAULT_TTL):
            os.remove(path)
            return None
        return payload["value"]
    except Exception:
        return None


def cache_set(key, value, ttl=DEFAULT_TTL):
    # FIX (implementacion): escritura atomica via fichero temporal + os.replace.
    # Antes se escribia directamente sobre el fichero final; con varios
    # workers de Celery concurrentes, una lectura simultanea podia toparse
    # con un JSON a medio escribir (corrupto) y fallar silenciosamente.
    path = _cache_path(key)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "ttl": ttl, "value": value}, f)
        os.replace(tmp_path, path)
    except Exception as e:
        logger.warning("Error escribiendo cache: %s", e)


def purge_expired_cache():
    now = time.time()
    for fname in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if now - payload["ts"] > payload.get("ttl", DEFAULT_TTL):
                os.remove(path)
        except Exception:
            try:
                os.remove(path)
            except Exception:
                pass