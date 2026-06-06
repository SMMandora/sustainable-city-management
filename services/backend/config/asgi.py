import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
django.setup()

from django.core.asgi import get_asgi_application  # noqa: E402

application = get_asgi_application()
