import importlib.util
import os
import sys
from enum import StrEnum
from importlib.metadata import entry_points
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import django.conf.locale
import importlib_metadata
from django.contrib.messages import constants as messages
from django.utils.translation import gettext_lazy as _
from kombu import Queue
from pycountry import currencies
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings as _BaseSettings
from pydantic_settings import PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from rich import print

from eventyay import __version__

# To avoid loading unnecessary environment variables
# designated for other applications
# we only load those with EVY_ prefix.
_ENV_PREFIX = 'EVY_'

# Use this environment variable to choose the running environment.
# Example: EVY_RUNNING_ENVIRONMENT=production ./manage.py runserver
_ENV_KEY_ACTIVE_ENVIRONMENT = 'EVY_RUNNING_ENVIRONMENT'

# Our system will look for these TOML configuration files:
# - eventyay.{active_environment}.toml
# - eventyay.local.toml
#
# The 'eventyay.{active_environment}.toml' is the main configuration file
# for current active environment.
# The 'eventyay.local.toml' is optional, ignored by Git, for developers to override settings
# to match their personal setup.
# Sensitive data like passwords, API keys should be put in ".secrets/" directory,
# where the file names match the setting names, prefixed with "EVY_".
# For example, to provide `secret_key`, create a file named ".secrets/EVY_SECRET_KEY".
# Ref: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#secrets

_DEFAULT_DB_NAME = 'eventyay-db'

BASE_DIR = Path(__file__).resolve().parent.parent
# The root directory of the project, where "./manage.py" file is located.
PROJECT_ROOT = BASE_DIR.parent
SECRETS_DIR = PROJECT_ROOT / '.secrets'


# To choose the running environment, pass via EVY_RUNNING_ENVIRONMENT.
# For example:
#   EVY_RUNNING_ENVIRONMENT=production ./manage.py runserver
class RunningEnvironment(StrEnum):
    PRODUCTION = 'production'
    DEVELOPMENT = 'development'
    TESTING = 'testing'


active_environment = RunningEnvironment(os.getenv(_ENV_KEY_ACTIVE_ENVIRONMENT, 'development'))
# Some shortcuts
is_development = active_environment == RunningEnvironment.DEVELOPMENT
is_testing = active_environment == RunningEnvironment.TESTING
is_production = active_environment == RunningEnvironment.PRODUCTION

DEFAULT_AUTH_BACKENDS = ('eventyay.base.auth.NativeAuthBackend',)
DEFAULT_PLUGINS = (
    'eventyay.plugins.sendmail',
    'eventyay.plugins.statistics',
    'eventyay.plugins.checkinlists',
    'eventyay.plugins.autocheckin',
)


class BaseSettings(_BaseSettings):
    """
    Contains the settings which were loaded from the configuration file.

    After that, the settings will be manipulated to serve Django.
    This class is named "BaseSettings" because the settings it holds are not finalized yet.
    Doc: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
    """

    # Tell Pydantic how to load our configurations.
    model_config = SettingsConfigDict(
        env_prefix=_ENV_PREFIX,
        env_file='.env',
        env_file_encoding='utf-8',
        secrets_dir=SECRETS_DIR,
    )
    # Here, starting our settings fields.
    # The names follow what is in Django and converted to lowercase.
    debug: bool = False
    secret_key: str = 'please-give-one-in-secret-file'
    postgres_db: str = _DEFAULT_DB_NAME
    # When these values are `None`, "peer" connection method will be used.
    # We just need to have a PostgreSQL user with the same name as Linux user.
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_host: str | None = None
    postgres_port: int | None = None
    redis_url: str = 'redis://localhost/0'
    language_code: str = 'en'
    # Don't send emails to Internet by default.
    email_backend: str = 'django.core.mail.backends.console.EmailBackend'
    email_host: str = 'localhost'
    email_port: int = 587
    email_host_user: str = 'info@eventyay.com'
    email_host_password: str = ''
    email_use_tls: bool = True
    default_from_email: str = 'info@eventyay.com'
    allowed_hosts: list[str] = []
    # Used by "Talk" (pretalx). Not sure why it is named like this.
    core_modules: Annotated[tuple[str, ...], Field(default_factory=tuple)]
    site_url: HttpUrl = 'http://localhost:8000'
    short_url: HttpUrl = 'http://localhost:8000'
    talk_hostname: str = 'http://localhost:8000'
    sentry_dsn: str = ''
    instance_name: str = 'eventyay'
    auth_backends: Annotated[tuple[str, ...], Field(default_factory=lambda: DEFAULT_AUTH_BACKENDS)]
    obligatory_2fa: bool = False
    plugins_default: Annotated[tuple[str, ...], Field(default_factory=lambda: DEFAULT_PLUGINS)]
    plugins_exclude: Annotated[tuple[str, ...], Field(default_factory=tuple)]
    metrics_enabled: bool = False
    metrics_user: str = 'metrics'
    metrics_passphrase: str = ''
    log_csp: bool = True
    csp_additional_header: str = ''
    nanocdn_url: HttpUrl | None = None
    zoom_key: str = ''
    zoom_secret: str = ''
    control_secret: str = ''
    statsd_host: str = ''
    statsd_port: int = 8125
    statsd_prefix: str = 'eventyay'
    twitter_client_id: str = ''
    twitter_client_secret: str = ''
    linkedin_client_id: str = ''
    linkedin_client_secret: str = ''
    # Ask to provide comments when making changes in the admin interface.
    admin_audit_comments_asked: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[_BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Insert the TOML which matches the running environment
        toml_files = discover_toml_files()
        file_list_for_display = [str(p.relative_to(Path.cwd())) for p in toml_files]
        print(f'Loading configuration from: [blue]{file_list_for_display}[/]', file=sys.stderr)
        toml_settings = TomlConfigSettingsSource(
            settings_cls,
            toml_file=toml_files,
        )
        if Path('.env').is_file():
            print('Loading additional configuration from: [blue].env[/]', file=sys.stderr)
        if SECRETS_DIR.is_dir() and (files := tuple(SECRETS_DIR.glob(f'{_ENV_PREFIX}*'))):
            secrets_for_display = [str(p.relative_to(Path.cwd())) for p in files]
            print(f'Loading secrets from: [blue]{secrets_for_display}[/]', file=sys.stderr)
        return (
            init_settings,
            toml_settings,
            # The following files will override values from TOML files.
            env_settings,
            # Though having TOML files, we still support .env file
            # because we need to share some settings with other tools.
            dotenv_settings,
            file_secret_settings,
        )


def discover_toml_files() -> list[Path]:
    """Discover TOML configuration files to be loaded.

    Where to search:
    - The same directory as this settings file.
    - In parent directories, go up until the base directory (containing manage.py).
    """
    toml_files: list[Path] = []
    current_dir = Path(__file__).resolve().parent
    names = [f'eventyay.{active_environment}.toml', 'eventyay.local.toml']
    while True:
        for name in names:
            candidate = current_dir / name
            if candidate.is_file():
                toml_files.append(candidate)
        if current_dir == PROJECT_ROOT:
            break
        current_dir = current_dir.parent
    # Sort the files so that the "local" file is loaded last,
    # and the one in the deepest directory is loaded first.
    toml_files.sort(key=lambda p: (1 if 'local' in p.name else 0, -len(p.parts)))
    return toml_files


def increase_redis_db(url: str, increment: int) -> str:
    """Increase the Redis database number in the given URL by the given increment.

    If the provided URL is missing DB number, we assume it is 0.
    """
    parsed = urlparse(url)
    try:
        db_number = int(parsed.path.lstrip('/')) + increment
    except ValueError:
        db_number = increment
    new_path = f'/{db_number}'
    new_url = parsed._replace(path=new_path).geturl()
    return new_url


conf = BaseSettings()

# --- Now, provide values to Django's settings. ---

# Note: DEBUG doesn't mean "development".
# Sometimes we need "debug" in production for troubleshooting,
# but please use with caution (it can reveal sensitive data like passwords, API keys).
DEBUG = conf.debug
SECRET_KEY = conf.secret_key

DATA_DIR = BASE_DIR / 'data'
LOG_DIR = DATA_DIR / 'logs'
MEDIA_ROOT = DATA_DIR / 'media'
PROFILE_DIR = DATA_DIR / 'profiles'

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
MEDIA_ROOT.mkdir(exist_ok=True)


# Database configuration
DATABASES = {
    'default': {
        # We don't support other DB backends than PostgreSQL,
        # because we need advanced features like UUID, ARRAY, JSONB fields.
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': conf.postgres_db,
        # When these values are `None`, "peer" connection method will be used.
        # We just need to have a PostgreSQL user with the same name as Linux user.
        'USER': conf.postgres_user,
        'PASSWORD': conf.postgres_password,
        'HOST': conf.postgres_host,
        'PORT': conf.postgres_port,
        'CONN_MAX_AGE': 120,
    }
}

_LIBRARY_APPS = (
    'bootstrap3',
    'corsheaders',
    'channels',
    'compressor',
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_filters',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'django_celery_beat',
    'django.forms',
    'djangoformsetjs',
    'django_pdb',
    'jquery',
    'rest_framework.authtoken',
    'rules.apps.AutodiscoverRulesConfig',
    'oauth2_provider',
    'statici18n',
    'rest_framework',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    'allauth.socialaccount.providers.mediawiki',
)

if DEBUG and importlib.util.find_spec('django_extensions'):
    _LIBRARY_APPS += ('django_extensions',)

if DEBUG and importlib.util.find_spec('debug_toolbar'):
    _LIBRARY_APPS += ('debug_toolbar',)

_OURS_APPS = (
    'eventyay.agenda',
    'eventyay.common',
    'eventyay.orga',
    'eventyay.api',
    'eventyay.base',
    'eventyay.cfp',
    'eventyay.control.ControlConfig',
    'eventyay.event',
    'eventyay.eventyay_common',
    'eventyay.features.live.LiveConfig',
    'eventyay.features.analytics.graphs.GraphsConfig',
    'eventyay.features.importers.ImportersConfig',
    'eventyay.storage.StorageConfig',
    'eventyay.features.social.SocialConfig',
    'eventyay.features.integrations.zoom.ZoomConfig',
    'eventyay.helpers',
    'eventyay.mail',
    'eventyay.multidomain',
    'eventyay.person',
    'eventyay.presale',
    'eventyay.plugins.socialauth',
    'eventyay.plugins.banktransfer',
    'eventyay.plugins.badges',
    'eventyay.plugins.sendmail',
    'eventyay.plugins.statistics',
    'eventyay.plugins.reports',
    'eventyay.plugins.checkinlists',
    'eventyay.plugins.manualpayment',
    'eventyay.plugins.returnurl',
    'eventyay.plugins.scheduledtasks',
    'eventyay.plugins.ticketoutputpdf',
    'eventyay.plugins.webcheckin',
    'eventyay.schedule',
    'eventyay.submission',
    # For now, this app is installed from "plugins" folder.
    # It needs the "tool.uv.sources" entry in pyproject.toml.
    'pretix_venueless',
)

PRETIX_PLUGINS_DEFAULT = conf.plugins_default

# TODO: Merge these two.
PRETIX_PLUGINS_EXCLUDE = conf.plugins_exclude
PLUGINS_EXCLUDE = PRETIX_PLUGINS_EXCLUDE

eps = importlib_metadata.entry_points()

# Pretix plugins
pretix_plugins = [ep.module for ep in eps.select(group='pretix.plugin') if ep.module not in PLUGINS_EXCLUDE]

# Pretalx plugins
pretalx_plugins = [ep.module for ep in eps.select(group='pretalx.plugin') if ep.module not in PLUGINS_EXCLUDE]

SAFE_PRETIX_PLUGINS = tuple(m for m in pretix_plugins if m not in {'pretix_venueless', 'pretix_pages'})

INSTALLED_APPS = _LIBRARY_APPS + SAFE_PRETIX_PLUGINS + _OURS_APPS

# TODO: What is it for?
ALL_PLUGINS = sorted(pretix_plugins + pretalx_plugins)

# For "Talk" (pretalx).
# TODO: May rename, because it is extended from something, not only "core" modules.
CORE_MODULES = (
    INSTALLED_APPS
    + conf.core_modules
    + (
        'eventyay.base',
        'eventyay.presale',
        'eventyay.control',
        'eventyay.plugins.checkinlists',
        'eventyay.plugins.reports',
    )
)

# TODO: This list is only for display. It should not be here.
PLUGINS = []
for entry_point in entry_points(group='pretalx.plugin'):
    PLUGINS.append(entry_point.module)

# TODO: What is it for?
LOADED_PLUGINS = {}
for module_name in ALL_PLUGINS:
    try:
        module = importlib.import_module(module_name)
        LOADED_PLUGINS[module_name] = module
    except ModuleNotFoundError as e:
        print(f'Plugin not found: {module_name} ({e})')
    except ImportError as e:
        print(f'Failed to import plugin {module_name}: {e}')


AUTH_USER_MODEL = 'base.User'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

_LIBRARY_MIDDLEWARES = (
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
)

if DEBUG and importlib.util.find_spec('debug_toolbar'):
    _LIBRARY_MIDDLEWARES += ('debug_toolbar.middleware.DebugToolbarMiddleware',)

_OURS_MIDDLEWARES = (
    'eventyay.base.middleware.CustomCommonMiddleware',
    'eventyay.common.middleware.SessionMiddleware',  # Add session handling
    'eventyay.common.middleware.MultiDomainMiddleware',  # Check which host is used and if it is valid
    'eventyay.common.middleware.EventPermissionMiddleware',  # Sets locales, request.event, available events, etc.
    'eventyay.common.middleware.CsrfViewMiddleware',  # Protect against CSRF attacks before forms/data are processed
    'eventyay.multidomain.middlewares.MultiDomainMiddleware',
    'eventyay.multidomain.middlewares.SessionMiddleware',
    'eventyay.multidomain.middlewares.CsrfViewMiddleware',
    'eventyay.control.middleware.PermissionMiddleware',
    'eventyay.control.middleware.AuditLogMiddleware',
    'eventyay.control.video.middleware.SessionMiddleware',
    'eventyay.control.video.middleware.AuthenticationMiddleware',
    'eventyay.control.video.middleware.MessageMiddleware',
    'eventyay.base.middleware.LocaleMiddleware',
    'eventyay.base.middleware.SecurityMiddleware',
    'eventyay.presale.middleware.EventMiddleware',
    'oauth2_provider.middleware.OAuth2TokenMiddleware',
    'eventyay.api.middleware.ApiScopeMiddleware',
)

MIDDLEWARE = _LIBRARY_MIDDLEWARES + _OURS_MIDDLEWARES


_CORE_TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

template_loaders = (
    (('django.template.loaders.cached.Loader', _CORE_TEMPLATE_LOADERS),) if is_production else _CORE_TEMPLATE_LOADERS
)

TEMPLATES = (
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': (DATA_DIR / 'templates',),
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.request',
                'django.template.context_processors.tz',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'eventyay.config.settings.instance_name',
                'eventyay.agenda.context_processors.is_html_export',
                'eventyay.common.context_processors.add_events',
                'eventyay.common.context_processors.locale_context',
                'eventyay.common.context_processors.messages',
                'eventyay.common.context_processors.system_information',
                'eventyay.orga.context_processors.orga_events',
                'eventyay.base.context.contextprocessor',
                'eventyay.control.context.contextprocessor',
                'eventyay.presale.context.contextprocessor',
                'eventyay.eventyay_common.context.contextprocessor',
                'django.template.context_processors.request',
            ],
            'loaders': template_loaders,
        },
    },
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': [
            BASE_DIR / 'jinja-templates',
        ],
        'OPTIONS': {
            'environment': 'eventyay.jinja.environment',
            'extensions': (
                'jinja2.ext.i18n',
                'jinja2.ext.do',
                'jinja2.ext.debug',
                'jinja2.ext.loopcontrols',
            ),
        },
    },
)

AUTHENTICATION_BACKENDS = (
    'rules.permissions.ObjectPermissionBackend',
    'django.contrib.auth.backends.ModelBackend',
)

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = (
    # In development, we don't need strong password validation.
    ()
    if is_development
    else (
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
    )
)

LANGUAGE_CODE = conf.language_code
# Due to an issue of drifting time in Celery, we don't allow to change TIME_ZONE yet.
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LOCALE_PATHS = (BASE_DIR / 'locale',)

# TODO: Move to consts.py
ALL_LANGUAGES = (
    ('en', _('English')),
    ('de', _('German')),
    ('de-formal', _('German (informal)')),
    ('ar', _('Arabic')),
    ('zh-hans', _('Chinese (simplified)')),
    ('da', _('Danish')),
    ('nl', _('Dutch')),
    ('nl-informal', _('Dutch (informal)')),
    ('fr', _('French')),
    ('fi', _('Finnish')),
    ('el', _('Greek')),
    ('it', _('Italian')),
    ('lv', _('Latvian')),
    ('pl', _('Polish')),
    ('pt-pt', _('Portuguese (Portugal)')),
    ('pt-br', _('Portuguese (Brazil)')),
    ('ru', _('Russian')),
    ('es', _('Spanish')),
    ('sw', _('Swahili')),
    ('tr', _('Turkish')),
    ('uk', _('Ukrainian')),
)
LANGUAGES_OFFICIAL = {'en', 'de', 'de-formal'}
LANGUAGES_INCUBATING = {'pl', 'fi', 'pt-br'}
LANGUAGES_RTL = {'ar', 'he', 'fa-ir'}
# TODO: Convert to tuple (some code still assumes LANGUAGES to be a list)
LANGUAGES = (
    [(k, v) for k, v in ALL_LANGUAGES if k not in LANGUAGES_INCUBATING] if is_production else list(ALL_LANGUAGES)
)

EXTRA_LANG_INFO = {
    'de-formal': {
        'bidi': False,
        'code': 'de-formal',
        'name': 'German (informal)',
        'name_local': 'Deutsch',
        'public_code': 'de',
    },
    'nl-informal': {
        'bidi': False,
        'code': 'nl-informal',
        'name': 'Dutch (informal)',
        'name_local': 'Nederlands',
        'public_code': 'nl',
    },
    'fr': {'bidi': False, 'code': 'fr', 'name': 'French', 'name_local': 'Français'},
    'lv': {'bidi': False, 'code': 'lv', 'name': 'Latvian', 'name_local': 'Latviešu'},
    'pt-pt': {
        'bidi': False,
        'code': 'pt-pt',
        'name': 'Portuguese',
        'name_local': 'Português',
    },
    'sw': {
        'bidi': False,
        'code': 'sw',
        'name': _('Swahili'),
        'name_local': 'Kiswahili',
    },
}

django.conf.locale.LANG_INFO.update(EXTRA_LANG_INFO)

# TODO: Find more data from pretalx and move to consts.py
LANGUAGES_INFORMATION = {
    'en': {
        'name': _('English'),
        'natural_name': 'English',
        'official': True,
        'percentage': 100,
    },
    'de': {
        'name': _('German'),
        'natural_name': 'Deutsch',
        'official': True,
        'percentage': 100,
        'path': 'de_DE',
    },
    'de-formal': {
        'name': _('German (formal)'),
        'natural_name': 'Deutsch',
        'official': True,
        'percentage': 100,
        'public_code': 'de',
        'path': 'de_Formal',
    },
    'ar': {
        'name': _('Arabic'),
        'natural_name': 'اَلْعَرَبِيَّةُ',
        'official': False,
        'percentage': 72,
    },
    'cs': {
        'name': _('Czech'),
        'natural_name': 'Čeština',
        'official': False,
        'percentage': 97,
    },
    'el': {
        'name': _('Greek'),
        'natural_name': 'Ελληνικά',
        'official': False,
        'percentage': 90,
    },
    'es': {
        'name': _('Spanish'),
        'natural_name': 'Español',
        'official': False,
        'percentage': 80,
    },
    'fa-ir': {
        'name': _('Persian'),
        'natural_name': 'قارسی',
        'official': False,
        'percentage': 99,
        'path': 'fa_IR',
        'public_code': 'fa_IR',
    },
    'fr': {
        'name': _('French'),
        'natural_name': 'Français',
        'official': False,
        'percentage': 98,
        'path': 'fr_FR',
    },
    'it': {
        'name': _('Italian'),
        'natural_name': 'Italiano',
        'official': False,
        'percentage': 95,
    },
    'ja-jp': {
        'name': _('Japanese'),
        'natural_name': '日本語',
        'official': False,
        'percentage': 69,
        'public_code': 'jp',
    },
    'nl': {
        'name': _('Dutch'),
        'natural_name': 'Nederlands',
        'official': False,
        'percentage': 88,
    },
    'pt-br': {
        'name': _('Brazilian Portuguese'),
        'natural_name': 'Português brasileiro',
        'official': False,
        'percentage': 89,
        'public_code': 'pt',
    },
    'pt-pt': {
        'name': _('Portuguese'),
        'natural_name': 'Português',
        'official': False,
        'percentage': 89,
        'public_code': 'pt',
    },
    'ru': {
        'name': _('Russian'),
        'natural_name': 'Русский',
        'official': True,
        'percentage': 0,
    },
    'sw': {
        'name': _('Swahili'),
        'natural_name': 'Kiswahili',
        'official': False,
        'percentage': 0,
    },
    'ua': {
        'name': _('Ukrainian'),
        'natural_name': 'Українська',
        'official': True,
        'percentage': 0,
    },
    'zh-hant': {
        'name': _('Traditional Chinese (Taiwan)'),
        'natural_name': '漢語',
        'official': False,
        'percentage': 66,
        'public_code': 'zh',
    },
    'zh-hans': {
        'name': _('Simplified Chinese'),
        'natural_name': '简体中文',
        'official': False,
        'percentage': 86,
        'public_code': 'zh',
    },
}

# Use Redis for caching
REDIS_URL = conf.redis_url

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    },
    'process': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    },
    # TODO: Remove. Use the 'default' cache everywhere.
    'redis': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'REDIS_CLIENT_KWARGS': {'health_check_interval': 30},
        },
    },
}

# Use Redis for session storage
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# TODO: Remove. Redis is always required.
HAS_REDIS = bool(REDIS_URL)

# TODO: Remove. Always use Redis Pub/Sub for Channels.
REDIS_USE_PUBSUB = True

CELERY_BROKER_URL = increase_redis_db(REDIS_URL, 1)
CELERY_RESULT_BACKEND = increase_redis_db(REDIS_URL, 2)
CELERY_TASK_ALWAYS_EAGER = is_testing
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_QUEUES = (
    Queue('default', routing_key='default.#'),
    Queue('longrunning', routing_key='longrunning.#'),
    Queue('background', routing_key='background.#'),
    Queue('notifications', routing_key='notifications.#'),
)
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ROUTES = {
    'eventyay.base.services.notifications.*': {'queue': 'notifications'},
    'eventyay.api.webhooks.*': {'queue': 'notifications'},
}

STATIC_ROOT = BASE_DIR / 'static.dist'
STATICFILES_DIRS = (
    (BASE_DIR / 'static' / 'webapp'),
    # Added to make sure root package static assets (e.g. pretixcontrol/scss/) are found
    (BASE_DIR / 'static'),
)
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

NANOCDN_URL = conf.nanocdn_url
default_storage_backend = (
    'eventyay.base.integrations.platforms.storage.nanocdn.NanoCDNStorage'
    if NANOCDN_URL
    else 'django.core.files.storage.FileSystemStorage'
)

STORAGES = {
    'default': {'BACKEND': default_storage_backend},
    'staticfiles': {
        'BACKEND': 'eventyay.base.storage.NoMapManifestStaticFilesStorage',
    },
}

# For django-statici18n
STATICI18N_ROOT = BASE_DIR / 'static'

FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o775
FILE_UPLOAD_PERMISSIONS = 0o644

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
)
COMPRESS_ENABLED = COMPRESS_OFFLINE = is_production
COMPRESS_CSS_FILTERS = (
    # CssAbsoluteFilter is incredibly slow, especially when dealing with our _flags.scss
    # However, we don't need it if we consequently use the static() function in Sass
    # 'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSCompressorFilter',
)

# Security settings
X_FRAME_OPTIONS = 'DENY'
# Video-Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
CSP_DEFAULT_SRC = ("'self'", "'unsafe-eval'")
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CORS_ORIGIN_REGEX_WHITELIST = (
    (
        r'^https?://([\w\-]+\.)?eventyay\.com$',  # Allow any subdomain of eventyay.com
        r'^https?://app-test\.eventyay\.com(:\d+)?$',  # Allow video-dev.eventyay.com with any port
        r'^https?://app\.eventyay\.com(:\d+)?$',  # Allow wikimania-live.eventyay.com with any port
    )
    if is_production
    else (
        r'^http://localhost$',
        r'^http://localhost:\d+$',
    )
)

# URL settings
ROOT_URLCONF = 'eventyay.multidomain.maindomain_urlconf'

INTERNAL_IPS = ('127.0.0.1', '::1')
ALLOWED_HOSTS = conf.allowed_hosts

EMAIL_BACKEND = conf.email_backend
EMAIL_HOST = conf.email_host
EMAIL_PORT = conf.email_port
EMAIL_HOST_USER = conf.email_host_user
EMAIL_HOST_PASSWORD = conf.email_host_password
EMAIL_USE_TLS = conf.email_use_tls
# Ref: https://docs.djangoproject.com/en/5.2/ref/settings/#email-use-ssl
EMAIL_USE_SSL = not conf.email_use_tls
# TODO: Move to consts.py and rename
EVENTYAY_EMAIL_NONE_VALUE = 'info@eventyay.com'
# TODO: `MAIL_FROM` is not a Django setting and seems to be duplicated with `DEFAULT_FROM_EMAIL`.
# Also, DEFAULT_FROM_EMAIL and SERVER_EMAIL are for different purposes. They should not be the same.
MAIL_FROM = SERVER_EMAIL = DEFAULT_FROM_EMAIL = conf.default_from_email

# TODO: Remove (why we need to use different values from default?)
SESSION_COOKIE_NAME = 'eventyay_session'
LANGUAGE_COOKIE_NAME = 'eventyay_language'
CSRF_COOKIE_NAME = 'eventyay_csrftoken'
# TODO: After merging eventyay-xxx componenents, we may not need this.
CSRF_TRUSTED_ORIGINS = ['http://localhost:1337', 'http://next.eventyay.com:1337', 'https://next.eventyay.com']
SESSION_COOKIE_HTTPONLY = True
# TODO: Remove. We always use Nginx or we are even behind CloudFlare,
# so trusting X-Forwarded-For is a must, if we want to get real client IP.
TRUST_X_FORWARDED_FOR = True

WSGI_APPLICATION = 'eventyay.config.wsgi.application'
ASGI_APPLICATION = 'eventyay.config.asgi.application'

_LOGGING_HANDLERS = {
    'console': {
        'level': 'DEBUG',
        'class': 'logging.StreamHandler',
        'formatter': 'verbose',
    },
    'rich': {
        'level': 'DEBUG',
        'class': 'rich.logging.RichHandler' if os.getenv('TERM') else 'logging.StreamHandler',
        'formatter': 'tiny' if os.getenv('TERM') else 'verbose',
    },
}
_LOGGING_FORMATTERS = {
    'verbose': {'format': '%(levelname)s %(asctime)s %(module)s: %(message)s'},
    'tiny': {
        'format': '%(message)s',
        'datefmt': '[%X]',
    },
}
_adaptive_console_handler = 'rich' if DEBUG else 'console'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'root': {
        'level': 'WARNING',
        'handlers': [_adaptive_console_handler],
    },
    'formatters': _LOGGING_FORMATTERS,
    'handlers': _LOGGING_HANDLERS,
    'loggers': {
        'django.db.backends': {
            'handlers': [_adaptive_console_handler],
            'level': 'WARNING',
            'propagate': False,
        },
        # Daphne always print color codes, so we bypass rich handler
        'django.channels.server': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False,
        },
        # We need it to debug permission issues.
        'rules': {
            'handlers': [_adaptive_console_handler],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'eventyay': {
            'handlers': [_adaptive_console_handler],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# NOTE: I skipped configuring sending errors via emails to developers.
# We should setup Sentry for error tracking later.

# --- Django allauth settings for social login ---

# NOTE: django-allauth changed some settings name. Check https://docs.allauth.org/en/dev/release-notes/recent.html
# ACCOUNT_LOGIN_METHODS = {'email'}
# ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'

SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True

SOCIALACCOUNT_ADAPTER = 'eventyay.plugins.socialauth.adapter.CustomSocialAccountAdapter'
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True

OAUTH2_PROVIDER_APPLICATION_MODEL = 'api.OAuthApplication'
OAUTH2_PROVIDER_GRANT_MODEL = 'api.OAuthGrant'
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = 'api.OAuthAccessToken'
OAUTH2_PROVIDER_ID_TOKEN_MODEL = 'api.OAuthIDToken'
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = 'api.OAuthRefreshToken'
OAUTH2_PROVIDER = {
    'SCOPES': {
        'profile': _('User profile only'),
        'read': _('Read access'),
        'write': _('Write access'),
    },
    'OAUTH2_VALIDATOR_CLASS': 'eventyay.api.oauth.Validator',
    'ALLOWED_REDIRECT_URI_SCHEMES': ['https'] if is_production else ['http', 'https'],
    'ACCESS_TOKEN_EXPIRE_SECONDS': 3600 * 24,
    'ROTATE_REFRESH_TOKEN': False,
    'PKCE_REQUIRED': False,
    'OIDC_RESPONSE_TYPES_SUPPORTED': ['code'],  # We don't support proper OIDC for now
}

# Channels (WebSocket) configuration
redis_connection_kwargs = {
    'retry': Retry(ExponentialBackoff(), 3),
    'health_check_interval': 30,
}
redis_hosts = [
    {
        'address': REDIS_URL,
        **redis_connection_kwargs,
    }
]
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': ('channels_redis.pubsub.RedisPubSubChannelLayer'),
        'CONFIG': {
            'hosts': redis_hosts,
            'prefix': 'eventyay:asgi:',
            'capacity': 10000,
        },
    },
}

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'eventyay.api.auth.api_auth.NoPermission',
    ],
    'UNAUTHENTICATED_USER': 'eventyay.api.auth.api_auth.AnonymousUser',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'PAGE_SIZE': 50,
    'DEFAULT_AUTHENTICATION_CLASSES': ('eventyay.api.auth.api_auth.EventTokenAuthentication',),
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'UNICODE_JSON': False,
}

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
# TODO: Remove.
BASE_PATH = ''

SITE_URL = str(conf.site_url)
SITE_NETLOC = urlparse(SITE_URL).netloc

LOGIN_URL = 'eventyay_common:auth.login'
LOGIN_URL_CONTROL = 'eventyay_common:auth.login'

# TODO: We should not need them (after merging eventyay-xxx components).
VIDEO_BASE_PATH = '/video'
WEBSOCKET_URL = '/ws/event/'
TALK_BASE_PATH = ''
LOGIN_REDIRECT_URL = '/control/video'

FILE_UPLOAD_DEFAULT_LIMIT = 10 * 1024 * 1024

FORM_RENDERER = 'eventyay.common.forms.renderers.TabularFormRenderer'

# TODO: Move to consts.py. It should not be dynamic, or it will cause generating DB migrations.
DEFAULT_CURRENCY = 'USD'
CURRENCY_PLACES = {
    # default is 2
    'BIF': 0,
    'CLP': 0,
    'DJF': 0,
    'GNF': 0,
    'JPY': 0,
    'KMF': 0,
    'KRW': 0,
    'MGA': 0,
    'PYG': 0,
    'RWF': 0,
    'VND': 0,
    'VUV': 0,
    'XAF': 0,
    'XOF': 0,
    'XPF': 0,
}
CURRENCIES = list(currencies)


HTMLEXPORT_ROOT = DATA_DIR / 'htmlexport'
HTMLEXPORT_ROOT.mkdir(exist_ok=True)

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
MESSAGE_TAGS = {
    messages.INFO: 'alert-info',
    messages.ERROR: 'alert-danger',
    messages.WARNING: 'alert-warning',
    messages.SUCCESS: 'alert-success',
}
BOOTSTRAP3 = {
    'success_css_class': '',
    'field_renderers': {
        'default': 'bootstrap3.renderers.FieldRenderer',
        'inline': 'bootstrap3.renderers.InlineFieldRenderer',
        'control': 'eventyay.control.forms.renderers.ControlFieldRenderer',
        'bulkedit': 'eventyay.control.forms.renderers.BulkEditFieldRenderer',
        'bulkedit_inline': 'eventyay.control.forms.renderers.InlineBulkEditFieldRenderer',
        'checkout': 'eventyay.presale.forms.renderers.CheckoutFieldRenderer',
    },
}

# TODO: The value is an URL (https://...) but the name is "hostname". Rename it.
# Also, after merging eventyay-xxx components, we may not need this.
TALK_HOSTNAME = conf.talk_hostname

# TODO: Remove, why we have to get this information from settings?
EVENTYAY_VERSION = __version__

# TODO: Remove.
# These values are used for channel layer group name. Why we need to name group with Git commit?
EVENTYAY_COMMIT = os.getenv('EVENTYAY_COMMIT_SHA', 'unknown')
EVENTYAY_ENVIRONMENT = os.getenv('EVENTYAY_ENVIRONMENT', 'unknown')

# Sentry configuration
SENTRY_DSN = conf.sentry_dsn
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[CeleryIntegration(), DjangoIntegration()],
        send_default_pii=False,
        debug=DEBUG,
        release=EVENTYAY_COMMIT if EVENTYAY_COMMIT != 'unknown' else None,
        environment=active_environment.value,
    )

# Multifactor authentication configuration
MULTIFACTOR = {
    'LOGIN_CALLBACK': False,
    'RECHECK': True,
    'RECHECK_MIN': 3600 * 24,
    'RECHECK_MAX': 3600 * 24 * 7,
    'FIDO_SERVER_ID': urlparse(SITE_URL).hostname,
    'FIDO_SERVER_NAME': 'Eventyay',
    'TOKEN_ISSUER_NAME': 'Eventyay',
    'U2F_APPID': SITE_URL,
    'FACTORS': ['FIDO2'],
    'FALLBACKS': {},
}

INSTANCE_NAME = conf.instance_name
EVENTYAY_REGISTRATION = True
EVENTYAY_PASSWORD_RESET = True
EVENTYAY_LONG_SESSIONS = True
# Ref: https://docs.pretix.eu/dev/development/api/auth.html
EVENTYAY_AUTH_BACKENDS = conf.auth_backends
EVENTYAY_ADMIN_AUDIT_COMMENTS = conf.admin_audit_comments_asked
EVENTYAY_OBLIGATORY_2FA = conf.obligatory_2fa
EVENTYAY_SESSION_TIMEOUT_RELATIVE = 3600 * 3
EVENTYAY_SESSION_TIMEOUT_ABSOLUTE = 3600 * 12
# TODO: Merge with above.
PRETIX_ADMIN_AUDIT_COMMENTS = EVENTYAY_ADMIN_AUDIT_COMMENTS
PRETIX_SESSION_TIMEOUT_RELATIVE = 3600 * 3
PRETIX_SESSION_TIMEOUT_ABSOLUTE = 3600 * 12
PRETIX_EMAIL_NONE_VALUE = EVENTYAY_EMAIL_NONE_VALUE

# TODO: The `pdftk` tool should be auto-detected.
PDFTK = ''

# Disable the feature for now.
PROFILING_RATE = 0

METRICS_ENABLED = conf.metrics_enabled
METRICS_USER = conf.metrics_user
METRICS_PASSPHRASE = conf.metrics_passphrase

LOG_CSP = conf.log_csp
CSP_ADDITIONAL_HEADER = conf.csp_additional_header

SHORT_URL = str(conf.short_url)
# TODO: Remove. Our views should calculate it from the current connected HTTP/HTTPS protocol,
# instead of relying on a setting.
WEBSOCKET_PROTOCOL = 'wss' if is_production else 'ws'

ZOOM_KEY = conf.zoom_key
ZOOM_SECRET = conf.zoom_secret
CONTROL_SECRET = conf.control_secret
STATSD_HOST = conf.statsd_host
STATSD_PORT = conf.statsd_port
STATSD_PREFIX = conf.statsd_prefix
TWITTER_CLIENT_ID = conf.twitter_client_id
TWITTER_CLIENT_SECRET = conf.twitter_client_secret
LINKEDIN_CLIENT_ID = conf.linkedin_client_id
LINKEDIN_CLIENT_SECRET = conf.linkedin_client_secret

FRONTEND_DIR = BASE_DIR / 'frontend'
VITE_DEV_SERVER_PORT = 8080
VITE_DEV_SERVER = f'http://localhost:{VITE_DEV_SERVER_PORT}'
VITE_DEV_MODE = False  # Set to False to use static files instead of dev server
VITE_IGNORE = False  # Used to ignore `collectstatic`/`rebuild`

# Not sure if they need to be configurable.
ENTROPY = {
    'order_code': 5,
    'ticket_secret': 32,
    'voucher_code': 16,
    'giftcard_secret': 12,
}

IS_HTML_EXPORT = False
HTMLEXPORT_ROOT = DATA_DIR / 'htmlexport'

# TODO: Move to consts.py
EVENTYAY_PRIMARY_COLOR = '#2185d0'
DEFAULT_EVENT_PRIMARY_COLOR = '#2185d0'
PRETIX_PRIMARY_COLOR = EVENTYAY_PRIMARY_COLOR
