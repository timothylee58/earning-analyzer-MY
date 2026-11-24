import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "apps.scraper",
    "apps.nlp",
    "apps.signals",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kuala_Lumpur"
USE_TZ = True

# NLP pipeline configuration
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
FINBERT_MODEL = os.environ.get("FINBERT_MODEL", "ProsusAI/finbert")
XLMR_MODEL = os.environ.get(
    "XLMR_MODEL", "cardiffnlp/twitter-xlm-roberta-base-sentiment"
)

# Directory for downloaded Bursa PDFs
PDF_DIR = BASE_DIR / "data" / "pdfs"

# Hosted inference remains the default. Local inference loads models on demand.
USE_LOCAL_INFERENCE = os.environ.get("USE_LOCAL_INFERENCE", "0") == "1"
