import environ
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize django-environ
env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, "django-insecure-local-dev-secret-key-for-xpand-12345"),
    ALLOWED_HOSTS=(list, ["*"]),
    DATABASE_URL=(str, "postgresql://xpand_user:xpand_password@localhost:5432/xpand"),
    REDIS_URL=(str, "redis://localhost:6379/0"),
    MSG91_AUTH_KEY=(str, ""),
    MSG91_OTP_TEMPLATE_ID=(str, ""),
    AWS_ACCESS_KEY_ID=(str, ""),
    AWS_SECRET_ACCESS_KEY=(str, ""),
    AWS_REGION_NAME=(str, "us-east-1"),
    AWS_SES_SENDER=(str, ""),
)

# Read environment file if it exists
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Third-party apps
    "corsheaders",
    
    # Local apps
    "apps.authentication.apps.AuthenticationConfig",
    "apps.profiles.apps.ProfilesConfig",
    "apps.links.apps.LinksConfig",
    "apps.leads.apps.LeadsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.profiles.context_processors.theme_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

import sys

# Detect if postgres database library and libpq wrapper are available
HAS_POSTGRES = False
if "test" not in sys.argv:
    try:
        import psycopg
        from psycopg.pq import import_from_libpq
        import_from_libpq()
        HAS_POSTGRES = True
    except (ImportError, Exception):
        HAS_POSTGRES = False

# Database connection details
if "test" in sys.argv or not HAS_POSTGRES:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "xpand-local-cache",
        }
    }
else:
    DATABASES = {
        "default": env.db(),
    }

    # Redis caching definitions
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": env("REDIS_URL"),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            }
        }
    }

# Authentication user model registration
AUTH_USER_MODEL = "authentication.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# External SMS & Email credentials
MSG91_AUTH_KEY = env("MSG91_AUTH_KEY")
MSG91_OTP_TEMPLATE_ID = env("MSG91_OTP_TEMPLATE_ID")

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_REGION_NAME = env("AWS_REGION_NAME")
AWS_SES_SENDER = env("AWS_SES_SENDER")

LOGIN_URL = "/auth/login/"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

