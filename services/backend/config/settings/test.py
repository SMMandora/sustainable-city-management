from .base import *

DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES["default"] = {
    **env.db_url(
        "DATABASE_URL",
        default="postgres://postgres:postgres@localhost:5432/scm_test",
    ),
    "ENGINE": "django.db.backends.postgresql",
}

CACHES["default"]["LOCATION"] = env("REDIS_URL", default="redis://localhost:6379/15")

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
