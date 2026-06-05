import structlog

from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

LOGGING["formatters"]["console"] = {
    "()": "structlog.stdlib.ProcessorFormatter",
    "processor": structlog.dev.ConsoleRenderer(colors=False),
}
LOGGING["handlers"]["console"]["formatter"] = "console"
