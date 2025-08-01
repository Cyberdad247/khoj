"""
Django settings for app project.

Generated by 'django-admin startproject' using Django 4.2.5.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

import atexit
import logging
import os
from pathlib import Path

from django.templatetags.static import static

from khoj.utils.helpers import is_env_var_true

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("KHOJ_DJANGO_SECRET_KEY", "!secret")

# Set KHOJ_DOMAIN to custom domain for production deployments.
KHOJ_DOMAIN = os.getenv("KHOJ_DOMAIN") or "khoj.dev"

# Set KHOJ_ALLOWED_DOMAIN to the i.p or domain of the Khoj service on the internal network.
# Useful to set when running the service behind a reverse proxy.
KHOJ_ALLOWED_DOMAIN = os.getenv("KHOJ_ALLOWED_DOMAIN", KHOJ_DOMAIN)
ALLOWED_HOSTS = [f".{KHOJ_ALLOWED_DOMAIN}", "localhost", "127.0.0.1", "[::1]", f"{KHOJ_ALLOWED_DOMAIN}"]

# All Subdomains of KHOJ_DOMAIN are trusted for CSRF
CSRF_TRUSTED_ORIGINS = [
    f"https://*.{KHOJ_DOMAIN}",
    f"https://{KHOJ_DOMAIN}",
    f"http://*.{KHOJ_DOMAIN}",
    f"http://{KHOJ_DOMAIN}",
]

DISABLE_HTTPS = is_env_var_true("KHOJ_NO_HTTPS")

# WARNING: Change this check only if you know what you are doing.
if not os.getenv("KHOJ_DOMAIN"):
    SESSION_COOKIE_DOMAIN = "localhost"
    CSRF_COOKIE_DOMAIN = "localhost"
else:
    # Production Settings
    SESSION_COOKIE_DOMAIN = KHOJ_DOMAIN
    CSRF_COOKIE_DOMAIN = KHOJ_DOMAIN
    if not DISABLE_HTTPS:
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if DISABLE_HTTPS:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

    # These need to be set to Lax in order to work with http in some browsers. See reference: https://docs.djangoproject.com/en/5.0/ref/settings/#std-setting-SESSION_COOKIE_SECURE
    COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SAMESITE = "Lax"
else:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SAMESITE = "None"

# Application definition

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "khoj.database.apps.DatabaseConfig",
    "unfold",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "phonenumber_field",
    "django_apscheduler",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "khoj.app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "DIRS": [os.path.join(BASE_DIR, "templates"), os.path.join(BASE_DIR, "templates", "account")],
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

ASGI_APPLICATION = "app.asgi.application"

CLOSE_CONNECTIONS_AFTER_REQUEST = True

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATA_UPLOAD_MAX_NUMBER_FIELDS = 20000

# Default PostgreSQL configuration
DB_NAME = os.getenv("POSTGRES_DB", "khoj")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

# Use pgserver if env var explicitly set to true
USE_EMBEDDED_DB = is_env_var_true("USE_EMBEDDED_DB")

if USE_EMBEDDED_DB:
    # Set up logging for pgserver
    logger = logging.getLogger("pgserver_django")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    try:
        import pgserver

        # Set up data directory
        PGSERVER_DATA_DIR = os.getenv("PGSERVER_DATA_DIR") or os.path.join(BASE_DIR, "pgserver_data")
        os.makedirs(PGSERVER_DATA_DIR, exist_ok=True)

        logger.info(f"Initializing embedded Postgres DB with data directory: {PGSERVER_DATA_DIR}")

        # Start server
        PGSERVER_INSTANCE = pgserver.get_server(PGSERVER_DATA_DIR)

        # Create pgvector extension, if not already exists
        PGSERVER_INSTANCE.psql("CREATE EXTENSION IF NOT EXISTS vector;")

        # Create database, if not already exists
        db_exists_result = PGSERVER_INSTANCE.psql(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}';")
        db_exists = "(1 row)" in db_exists_result  # Check for actual row in result
        if not db_exists:
            logger.info(f"Creating database: {DB_NAME}")
            PGSERVER_INSTANCE.psql(f"CREATE DATABASE {DB_NAME};")

        # Register cleanup
        def cleanup_pgserver():
            if PGSERVER_INSTANCE:
                logger.debug("Shutting down embedded Postgres DB")
                PGSERVER_INSTANCE.cleanup()

        atexit.register(cleanup_pgserver)

        # Update database configuration for pgserver
        DB_HOST = PGSERVER_DATA_DIR
        DB_PORT = ""  # pgserver uses Unix socket, so port is empty

        logger.info("Embedded Postgres DB started successfully")

    except Exception as e:
        logger.error(f"Error initializing embedded Postgres DB: {str(e)}. Use standard PostgreSQL server.")

# Set the database configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "NAME": DB_NAME,
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": True,
    }
}

# User Settings
AUTH_USER_MODEL = "database.KhojUser"

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_ROOT = BASE_DIR / "static"
STATICFILES_DIRS = [
    BASE_DIR / "interface/web",
    BASE_DIR / "interface/email",
    BASE_DIR / "interface/built",
    BASE_DIR / "interface/compiled",
]
STATIC_URL = "/static/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Format string for displaying run time timestamps in the Django admin site. The default
# just adds seconds to the standard Django format, which is useful for displaying the timestamps
# for jobs that are scheduled to run on intervals of less than one minute.
#
# See https://docs.djangoproject.com/en/dev/ref/settings/#datetime-format for format string
# syntax details.
APSCHEDULER_DATETIME_FORMAT = "N j, Y, f:s a"

# Maximum run time allowed for jobs that are triggered manually via the Django admin site, which
# prevents admin site HTTP requests from timing out.
#
# Longer running jobs should probably be handed over to a background task processing library
# that supports multiple background worker processes instead (e.g. Dramatiq, Celery, Django-RQ,
# etc. See: https://djangopackages.org/grids/g/workers-queues-tasks/ for popular options).
APSCHEDULER_RUN_NOW_TIMEOUT = 240  # Seconds

UNFOLD = {
    "SITE_TITLE": "Khoj Admin Panel",
    "SITE_HEADER": "Khoj Admin Panel",
    "SITE_URL": "/",
    "SITE_ICON": {
        "light": lambda request: static("assets/icons/khoj_lantern_128x128.png"),
        "dark": lambda request: static("assets/icons/khoj_lantern_128x128_dark.png"),
    },
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/svg+xml",
            "href": lambda request: static("assets/icons/khoj_lantern.svg"),
        },
    ],
}
