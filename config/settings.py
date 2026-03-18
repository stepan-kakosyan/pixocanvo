import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
CSRF_TRUSTED_ORIGINS = os.getenv(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "https://*.yatuk.am").split(",")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "Notifications",
    "pixelwar",
    "users",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "Notifications.context_processors.notification_center",
                "pixelwar.context_processors.language_switcher_options",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE"),
        "USER": os.getenv("MYSQL_USER"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD"),
        "HOST": os.getenv("MYSQL_HOST"),
        "PORT": os.getenv("MYSQL_PORT"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}

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

LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("zh-hans", "Chinese"),
    ("es", "Spanish"),
    ("ar", "Arabic"),
    ("pt", "Portuguese"),
    ("id", "Indonesian"),
    ("fr", "French"),
    ("ja", "Japanese"),
    ("ru", "Russian"),
    ("de", "German"),
    ("ko", "Korean"),
    ("hi", "Hindi"),
    ("bn", "Bengali"),
    ("it", "Italian"),
    ("tr", "Turkish"),
    ("vi", "Vietnamese"),
    ("th", "Thai"),
    ("pl", "Polish"),
    ("nl", "Dutch"),
    ("uk", "Ukrainian"),
    ("hy", "Armenian"),
    ("ka", "Georgian"),
]

LANGUAGE_SWITCHER_OPTIONS = [
    ("en", "English (US)", "us"),
    ("en", "English (UK)", "gb"),
    ("zh-hans", "中文（简体）", "cn"),
    ("es", "Español", "es"),
    ("ar", "العربية", "sa"),
    ("pt", "Português", "br"),
    ("id", "Bahasa Indonesia", "id"),
    ("fr", "Français", "fr"),
    ("ja", "日本語", "jp"),
    ("ru", "Русский", "ru"),
    ("de", "Deutsch", "de"),
    ("ko", "한국어", "kr"),
    ("hi", "हिन्दी", "in"),
    ("bn", "বাংলা", "bd"),
    ("it", "Italiano", "it"),
    ("tr", "Türkçe", "tr"),
    ("vi", "Tiếng Việt", "vn"),
    ("th", "ไทย", "th"),
    ("pl", "Polski", "pl"),
    ("nl", "Nederlands", "nl"),
    ("uk", "Українська", "ua"),
    ("hy", "Հայերեն", "am"),
    ("ka", "ქართული", "ge"),
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.getenv("CHANNEL_REDIS_URL", "redis://redis:6379/2")],
        },
    }
}

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_PIXEL_TOPIC = os.getenv("KAFKA_PIXEL_TOPIC", "pixel-updates")
KAFKA_CHAT_TOPIC = os.getenv("KAFKA_CHAT_TOPIC", "chat-messages")
KAFKA_PRODUCER_CONNECT_ATTEMPTS = int(
    os.getenv("KAFKA_PRODUCER_CONNECT_ATTEMPTS", "10")
)
KAFKA_PRODUCER_RETRY_BACKOFF = float(
    os.getenv("KAFKA_PRODUCER_RETRY_BACKOFF", "1.0")
)
KAFKA_PRODUCER_SEND_TIMEOUT = float(
    os.getenv("KAFKA_PRODUCER_SEND_TIMEOUT", "3.0")
)
KAFKA_CONSUMER_GROUP_ID = os.getenv(
    "KAFKA_CONSUMER_GROUP_ID",
    "pixel-db-consumers-v1",
)
KAFKA_CONSUMER_AUTO_OFFSET_RESET = os.getenv(
    "KAFKA_CONSUMER_AUTO_OFFSET_RESET",
    "earliest",
)
KAFKA_CONSUMER_CONNECT_RETRY_BACKOFF = float(
    os.getenv("KAFKA_CONSUMER_CONNECT_RETRY_BACKOFF", "2.0")
)
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    os.getenv("REDIS_URL", "redis://redis:6379/1"),
)
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    CELERY_BROKER_URL,
)
CELERY_TASK_IGNORE_RESULT = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
COOLDOWN_SECONDS = int(os.getenv("PIXEL_COOLDOWN_SECONDS", "60"))
INITIAL_GRID_SIZE = int(os.getenv("PIXEL_INITIAL_GRID_SIZE", "200"))
GRID_EXPAND_STEP = int(os.getenv("PIXEL_GRID_EXPAND_STEP", "20"))
GRID_FILL_EXPAND_THRESHOLD = float(
    os.getenv("PIXEL_GRID_FILL_EXPAND_THRESHOLD", "0.8")
)
GRID_MAX_SIZE = int(os.getenv("PIXEL_GRID_MAX_SIZE", "1000"))

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "0") == "1"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")
PASSWORD_RESET_TIMEOUT = int(
    os.getenv("EMAIL_ACTIVATION_TIMEOUT_SECONDS", "86400")
)
PASSWORD_RESET_LINK_TTL_SECONDS = int(
    os.getenv("PASSWORD_RESET_LINK_TTL_SECONDS", "1800")
)
