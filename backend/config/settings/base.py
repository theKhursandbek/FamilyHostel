"""
Django base settings for Hostel Management System.

Shared settings for all environments (development, production).
Reference: hostel_telegram_mini_app_readme.md
"""

import environ
from datetime import timedelta
from pathlib import Path

# ==============================================================================
# PATH CONFIGURATION
# ==============================================================================

# backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ==============================================================================
# ENVIRONMENT VARIABLES
# ==============================================================================

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR / ".env")

# ==============================================================================
# CORE SETTINGS
# ==============================================================================

SECRET_KEY = env("SECRET_KEY")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ==============================================================================
# APPLICATION DEFINITION
# ==============================================================================

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "corsheaders",
    "channels",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.branches",
    "apps.bookings",
    "apps.staff",
    "apps.admin_panel",
    "apps.cleaning",
    "apps.payments",
    "apps.reports",
    "apps.backups",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ==============================================================================
# MIDDLEWARE
# ==============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.security.middleware.SecurityLoggingMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.security.middleware.BlockedUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "config.security.middleware.SecurityHeadersMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ==============================================================================
# URL CONFIGURATION
# ==============================================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"

# ==============================================================================
# TEMPLATES
# ==============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ==============================================================================
# DATABASE — PostgreSQL (README Section 2 & 16.3)
# ==============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),  # type: ignore[call-overload]
        "USER": env("DB_USER"),  # type: ignore[call-overload]
        "PASSWORD": env("DB_PASSWORD"),  # type: ignore[call-overload]
        "HOST": env("DB_HOST"),  # type: ignore[call-overload]
        "PORT": env("DB_PORT"),  # type: ignore[call-overload]
        "ATOMIC_REQUESTS": True,
    }
}

# ==============================================================================
# AUTHENTICATION — Custom Account Model (README Section 14.1)
# ==============================================================================

AUTH_USER_MODEL = "accounts.Account"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ==============================================================================
# INTERNATIONALIZATION — Uzbekistan (README Section 15)
# ==============================================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Tashkent"  # UTC+5

USE_I18N = True

USE_TZ = True

# ==============================================================================
# STATIC & MEDIA FILES
# ==============================================================================

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ==============================================================================
# DJANGO REST FRAMEWORK (README Section 16.2 & 17)
# ==============================================================================

REST_FRAMEWORK = {
    # Pagination (Step 20)
    "DEFAULT_PAGINATION_CLASS": "config.api.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    # Authentication — JWT primary, session for browsable API (README Section 25.5)
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Throttling — rate limiting (README Section 16.6 & 26.5)
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "100/minute",
        "auth": "10/minute",
    },
    # Renderer — wraps success responses in {success: true, data: ...} (Step 20)
    "DEFAULT_RENDERER_CLASSES": [
        "config.api.renderers.StandardJSONRenderer",
    ],
    # Filtering, ordering, search (Step 20)
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    # Exception handler — wraps errors in {success: false, error: ...} (Step 20)
    "EXCEPTION_HANDLER": "config.api.exception_handler.custom_exception_handler",
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%z",
}

# ==============================================================================
# CORS
# ==============================================================================

CORS_ALLOWED_ORIGINS = []

CORS_ALLOW_CREDENTIALS = True

# ==============================================================================
# JWT — djangorestframework-simplejwt (README Section 25.5 & 26.5)
# ==============================================================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ==============================================================================
# STRIPE (README Section 25.1 & 26.1)
# ==============================================================================

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")  # type: ignore[call-overload]
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")  # type: ignore[call-overload]

# ==============================================================================
# TELEGRAM BOT (README Section 26.4)
# ==============================================================================

TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")  # type: ignore[call-overload]

# ==============================================================================
# CELERY — Background task queue (Step 17)
# ==============================================================================

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")  # type: ignore[call-overload]
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/0")  # type: ignore[call-overload]
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4 minutes soft limit
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Fail fast when the broker (Redis) is unreachable instead of blocking the
# request thread that called `.delay()`.  Without these settings kombu retries
# the broker connection forever, which would freeze any view that publishes
# a Celery task while Redis is offline.
CELERY_BROKER_CONNECTION_TIMEOUT = 2          # seconds to open a TCP connection
CELERY_BROKER_CONNECTION_RETRY = False         # don't keep retrying on publish
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
CELERY_BROKER_CONNECTION_MAX_RETRIES = 0
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "socket_timeout": 2,
    "socket_connect_timeout": 2,
}

# Result-backend hardening: when the producer publishes a task it must NOT
# subscribe to a result channel synchronously — that path also touches Redis
# and would block the request thread when Redis is offline.
CELERY_TASK_IGNORE_RESULT = True
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    "socket_timeout": 2,
    "socket_connect_timeout": 2,
    "retry_policy": {"timeout": 2.0, "max_retries": 0},
}

# ==============================================================================
# CELERY BEAT — Scheduled tasks (Step 26)
# ==============================================================================

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "backup-daily": {
        "task": "backups.daily_backup",
        "schedule": crontab(hour=2, minute=0),  # every day at 02:00
    },
    "backup-weekly": {
        "task": "backups.weekly_backup",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 03:00
    },
    "auto-complete-due-bookings": {
        # Auto-checkout paid bookings whose check_out_date has arrived.
        "task": "bookings.auto_complete_due_bookings",
        "schedule": crontab(hour=12, minute=0),  # every day at 12:00
    },
}

# ==============================================================================
# BACKUP SYSTEM (Step 26)
# ==============================================================================

# Backend: "local" (filesystem) or "azure" (Azure Blob Storage)
BACKUP_STORAGE_BACKEND = env("BACKUP_STORAGE_BACKEND", default="local")  # type: ignore[call-overload]

# Local backup directory (default: backend/backups/)
BACKUP_LOCAL_DIR = BASE_DIR / "backups"

# Azure Blob backup credentials (re-uses media Azure creds if not overridden)
BACKUP_AZURE_ACCOUNT_NAME = env("BACKUP_AZURE_ACCOUNT_NAME", default="")  # type: ignore[call-overload]
BACKUP_AZURE_ACCOUNT_KEY = env("BACKUP_AZURE_ACCOUNT_KEY", default="")  # type: ignore[call-overload]
BACKUP_AZURE_CONTAINER = env("BACKUP_AZURE_CONTAINER", default="backups")  # type: ignore[call-overload]

# Retention policy — how many backups to keep per type
BACKUP_RETENTION = {
    "daily": 7,
    "weekly": 4,
}

# ==============================================================================
# DJANGO CHANNELS — WebSocket real-time layer (Step 21.4)
# ==============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://localhost:6379/1")],  # type: ignore[call-overload]
            # Fail fast when Redis is unreachable so a dead broker can't
            # block request threads that publish dashboard events.
            "symmetric_encryption_keys": [],
            "capacity": 1500,
            "expiry": 60,
        },
    },
}

# ==============================================================================
# DEFAULT PRIMARY KEY
# ==============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==============================================================================
# LOGGING — Security events (README Section 23)
# ==============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "security": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "security_console": {
            "class": "logging.StreamHandler",
            "formatter": "security",
        },
    },
    "loggers": {
        "security": {
            "handlers": ["security_console"],
            "level": "WARNING",
            "propagate": False,
        },
        "backups": {
            "handlers": ["security_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
