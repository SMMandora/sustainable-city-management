import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("scm")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "ingest-dublin-bikes": {
        "task": "apps.ingestion.tasks.poll_source",
        "schedule": 60.0,
        "args": ("dublin_bikes",),
        "options": {"expires": 55},
    },
}
