import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY   = os.environ.get("SECRET_KEY", "django-insecure-change-me-in-production")
DEBUG        = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.routing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

DATABASES = {
    "default": {
        "ENGINE":   "django.db.backends.postgresql",
        "NAME":     os.environ.get("POSTGRES_DB",       "fuel_route"),
        "USER":     os.environ.get("POSTGRES_USER",     "fuel_user"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "fuel_pass"),
        "HOST":     os.environ.get("POSTGRES_HOST",     "db"),
        "PORT":     os.environ.get("POSTGRES_PORT",     "5432"),
    }
}

STATIC_URL         = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    # Public, auth-free API — disable auth so we don't depend on django.contrib.auth
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}
