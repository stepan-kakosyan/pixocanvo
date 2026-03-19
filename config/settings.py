import os
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

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
    "storages",
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


def env_bool(name: str, default: bool = False) -> bool:
    default_value = "1" if default else "0"
    return os.getenv(name, default_value) == "1"


def build_s3_base_url(
    bucket_name: str,
    region_name: str,
    custom_domain: str,
    endpoint_url: str,
) -> str:
    if custom_domain:
        return f"https://{custom_domain.strip('/')}"

    if endpoint_url:
        return f"{endpoint_url.rstrip('/')}/{bucket_name}"

    if region_name and region_name != "us-east-1":
        return f"https://{bucket_name}.s3.{region_name}.amazonaws.com"

    return f"https://{bucket_name}.s3.amazonaws.com"


USE_S3 = env_bool("USE_S3")
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
STATIC_URL = "/static/"
MEDIA_URL = "/media/"

if USE_S3:
    aws_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME", "").strip()
    aws_region_name = os.getenv("AWS_S3_REGION_NAME", "").strip()
    aws_custom_domain = os.getenv("AWS_S3_CUSTOM_DOMAIN", "").strip()
    aws_endpoint_url = os.getenv("AWS_S3_ENDPOINT_URL", "").strip()
    aws_static_location = os.getenv("AWS_STATIC_LOCATION", "static")
    aws_media_location = os.getenv("AWS_MEDIA_LOCATION", "media")
    aws_static_location = aws_static_location.strip("/") or "static"
    aws_media_location = aws_media_location.strip("/") or "media"

    if not aws_bucket_name:
        raise ImproperlyConfigured(
            "AWS_STORAGE_BUCKET_NAME must be set when USE_S3=1."
        )

    s3_options = {
        "bucket_name": aws_bucket_name,
        "default_acl": None,
        "file_overwrite": env_bool("AWS_S3_FILE_OVERWRITE"),
        "querystring_auth": env_bool("AWS_QUERYSTRING_AUTH"),
    }

    if aws_region_name:
        s3_options["region_name"] = aws_region_name

    if aws_custom_domain:
        s3_options["custom_domain"] = aws_custom_domain

    if aws_endpoint_url:
        s3_options["endpoint_url"] = aws_endpoint_url

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                **s3_options,
                "location": aws_media_location,
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                **s3_options,
                "location": aws_static_location,
            },
        },
    }

    aws_base_url = build_s3_base_url(
        aws_bucket_name,
        aws_region_name,
        aws_custom_domain,
        aws_endpoint_url,
    )
    STATIC_URL = f"{aws_base_url}/{aws_static_location}/"
    MEDIA_URL = f"{aws_base_url}/{aws_media_location}/"

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
