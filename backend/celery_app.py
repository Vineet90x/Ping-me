"""Celery application for background jobs (appointment reminders, broadcasts).

Run a worker:   celery -A celery_app.celery_app worker --loglevel=info
Run the beat:   celery -A celery_app.celery_app beat   --loglevel=info
"""
from celery import Celery
from celery.schedules import crontab

from config import REDIS_URL

celery_app = Celery(
    "ping",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"],
)

celery_app.conf.update(
    timezone="Asia/Kolkata",
    enable_utc=False,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "send-appointment-reminders": {
        "task": "tasks.send_due_reminders",
        "schedule": crontab(minute="*/15"),  # every 15 minutes
    },
    "notify-unpaid-invoices": {
        "task": "tasks.notify_unpaid_invoices",
        "schedule": crontab(hour=11, minute=0),  # once a day, 11:00 IST
    },
}
