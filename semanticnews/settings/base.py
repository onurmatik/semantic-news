import os
from pathlib import Path

from dotenv import load_dotenv

from django.utils.translation import gettext_lazy as _

# Build paths inside the project like this: BASE_DIR / 'subdir'.
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = PACKAGE_ROOT.parent


def _load_local_env() -> None:
    """Load environment variables from a local .env file if present."""

    env_path = BASE_DIR / '.env'
    if not env_path.exists():
        env_path = PACKAGE_ROOT / '.env'
    if env_path.exists():
        load_dotenv(env_path)


_load_local_env()


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-w7h0dw4!8vjodxdnovwd7j9qhn^$f#t%%%u^4lt5k51k9-f1y+'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True


ALLOWED_HOSTS = ['localhost']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    'widget_tweaks',

    'semanticnews.profiles',
    'semanticnews.agenda',
    'semanticnews.entities',
    'semanticnews.contents',

    # User topics and widget apps
    'semanticnews.widgets',
    'semanticnews.topics',
    'semanticnews.widgets.recaps',
    'semanticnews.widgets.text',
    'semanticnews.widgets.mcps',
    'semanticnews.widgets.images',
    'semanticnews.widgets.data',
    'semanticnews.widgets.webcontent',
    'semanticnews.widgets.timeline',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'semanticnews.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [PACKAGE_ROOT / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'libraries': {
                'language_tags': 'semanticnews.templatetags.language_tags',
            },
        },
    },
]

WSGI_APPLICATION = 'semanticnews.wsgi.application'


# Database: PostgreSQL is required for vector fields

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME', 'semanticnews'),
        'USER': os.getenv('DATABASE_USER'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD'),
        'HOST': os.getenv('DATABASE_HOST', 'localhost'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

LANGUAGES = [
    ("en", _("English")),
]

LOCALE_PATHS = [PACKAGE_ROOT / 'locale']


# Locality configuration
DEFAULT_LOCALITY = "global"
LOCALITIES = [
    ("global", _("Global")),
]


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')

if AWS_STORAGE_BUCKET_NAME:
    STORAGES = {
        "default": {  # user uploaded media files
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "location": "media",
                "file_overwrite": False
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "location": "static",
                "file_overwrite": True,
                "querystring_auth": False,
            },
        },
    }

    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"

    AWS_QUERYSTRING_AUTH = False  # so URLs are public
    AWS_DEFAULT_ACL = None  # needed to avoid ACL errors

else:
    # Local dev setup
    STATIC_URL = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"

    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

# Static files directory for development
_static_dirs = [BASE_DIR / 'static', PACKAGE_ROOT / 'static']
STATICFILES_DIRS = tuple(str(path) for path in _static_dirs if path.exists())


# AI / LLM configuration
DEFAULT_AI_MODEL = os.getenv("DEFAULT_AI_MODEL", "gpt-5-nano")

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "semanticnews.openai": {"handlers": ["console"], "level": "DEBUG"},
    },
}


LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Celery configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
CELERY_TASK_DEFAULT_QUEUE = "sn"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Load env specific settings
# Equivalent of "from .ENV_NAME import *"

from importlib import import_module

ENV_NAME = os.getenv("ENV_NAME", "local")

try:
    module = import_module(f".{ENV_NAME}", package=__package__)
except ImportError:
    pass
else:
    globals().update(vars(module))
