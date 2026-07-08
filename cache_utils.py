import os
import json
import logging
import redis

logger = logging.getLogger("plagiarism_checker")

# Reutilizamos la URL de Redis configurada en el entorno
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
# Conexión dedicada para la caché (usamos la db 2 de Redis para no colisionar con Celery)
redis_client = redis.from_url(REDIS_URL, db=2)

DEFAULT_TTL = 60 * 60 * 24  # 24 horas

def cache_get(key):
    try:
        cached_data = redis_client.get(key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        logger.warning("Error leyendo de Redis cache: %s", e)
    return None

def cache_set(key, value, ttl=DEFAULT_TTL):
    try:
        # setex guarda el valor e impone el TTL de forma nativa y atómica
        redis_client.setex(key, ttl, json.dumps(value))
    except Exception as e:
        logger.warning("Error escribiendo en Redis cache: %s", e)

def purge_expired_cache():
    # Con Redis esto ya no es necesario; los elementos expiran automáticamente.
    pass