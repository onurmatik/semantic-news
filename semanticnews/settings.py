import json
import os
from pathlib import Path
from dotenv import load_dotenv

from django.utils.translation import gettext_lazy as _, get_language_info, to_language

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env for local development
load_dotenv(BASE_DIR / '.env')


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-w7h0dw4!8vjodxdnovwd7j9qhn^$f#t%%%u^4lt5k51k9-f1y+'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', True)

HOST = os.getenv('HOST', 'localhost')

ALLOWED_HOSTS = [HOST]

# Site branding
SITE_TITLE = os.getenv("SITE_TITLE", "Semantic.news")
SITE_LOGO = os.getenv("SITE_LOGO", "logo.png")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    'semanticnews.profiles',
    'semanticnews.agenda',
    'semanticnews.entities',
    'semanticnews.contents',

    # User topics and utility apps
    'semanticnews.topics',
    'semanticnews.topics.utils.recaps',
    'semanticnews.topics.utils.narratives',
    'semanticnews.topics.utils.mcps',
    'semanticnews.topics.utils.images',
    'semanticnews.topics.utils.embeds',
    'semanticnews.topics.utils.relations',
    'semanticnews.topics.utils.data',
    'semanticnews.topics.utils.documents',
    'semanticnews.topics.utils.timeline',
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
        'DIRS': [os.path.join(BASE_DIR, 'semanticnews/templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'semanticnews.context_processors.branding',
            ],
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


def _normalize_language_code(code: str) -> str:
    """Return a normalized Django language code."""

    if not code:
        return ""

    return to_language(code.replace("_", "-"))


def _parse_supported_languages(value: str) -> list[str]:
    """Parse SUPPORTED_LANGUAGES from the environment."""

    if not value:
        return []

    value = value.strip()
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = [item.strip() for item in value.split(",")]
    else:
        if isinstance(parsed, str):
            parsed = [parsed]
        elif isinstance(parsed, dict):
            parsed = list(parsed.keys())
        elif not isinstance(parsed, (list, tuple)):
            parsed = []

    languages = []
    for item in parsed:
        if isinstance(item, str):
            normalized = _normalize_language_code(item)
            if normalized:
                languages.append(normalized)

    return languages


DEFAULT_LANGUAGE = _normalize_language_code(os.getenv("DEFAULT_LANGUAGE"))
SUPPORTED_LANGUAGES = _parse_supported_languages(os.getenv("SUPPORTED_LANGUAGES"))

if not SUPPORTED_LANGUAGES:
    SUPPORTED_LANGUAGES = [
        _normalize_language_code(code)
        for code in ("en", "tr")
    ]

SUPPORTED_LANGUAGES = [code for code in SUPPORTED_LANGUAGES if code]

if not DEFAULT_LANGUAGE:
    DEFAULT_LANGUAGE = SUPPORTED_LANGUAGES[0] if SUPPORTED_LANGUAGES else "en"

DEFAULT_LANGUAGE = _normalize_language_code(DEFAULT_LANGUAGE) or "en"

if DEFAULT_LANGUAGE not in SUPPORTED_LANGUAGES:
    SUPPORTED_LANGUAGES.insert(0, DEFAULT_LANGUAGE)

# Ensure ordering is preserved while removing duplicates
seen_languages: list[str] = []
for lang_code in SUPPORTED_LANGUAGES:
    if lang_code and lang_code not in seen_languages:
        seen_languages.append(lang_code)

SUPPORTED_LANGUAGES = tuple(seen_languages)

DEFAULT_LANGUAGE = seen_languages[0] if seen_languages else "en"
LANGUAGE_CODE = DEFAULT_LANGUAGE


def _get_language_name(code: str) -> str:
    """Return a localized display name for the language."""

    try:
        info = get_language_info(code)
    except KeyError:
        base_code = code.split("-", 1)[0]
        if base_code and base_code != code:
            try:
                info = get_language_info(base_code)
            except KeyError:
                info = None
        else:
            info = None

    if info:
        return info.get("name_local") or info.get("name") or code

    return code


LANGUAGES = tuple((code, _(_get_language_name(code))) for code in SUPPORTED_LANGUAGES)

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [BASE_DIR / 'locale']


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
    STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

    MEDIA_URL = "/media/"
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Static files directory for development
STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static'),)


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
