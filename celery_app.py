import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv


load_dotenv()


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Europe/Madrid")


celery = Celery(
    "plagiarism_checker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"]
)


celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=APP_TIMEZONE,
    enable_utc=True,
    worker_concurrency=int(os.environ.get("CELERY_CONCURRENCY", 2)),
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True
)

celery.conf.beat_schedule = {
    "purge-old-jobs-daily": {
        "task": "tasks.purge_old_jobs_task",
        "schedule": crontab(hour=3, minute=0),
    },
}