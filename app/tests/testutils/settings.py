import atexit
import os
import tempfile

tmpdir = tempfile.TemporaryDirectory()
os.environ.setdefault('DATA_DIR', tmpdir.name)

from eventyay.config.settings import *  # NOQA,F401,F403

# Make these mutable for test-specific overrides.
INSTALLED_APPS = list(INSTALLED_APPS)
TEMPLATES = list(TEMPLATES)
TEMPLATES[0] = dict(TEMPLATES[0])
TEMPLATES[0]['DIRS'] = list(TEMPLATES[0]['DIRS'])
TEMPLATES[0]['OPTIONS'] = dict(TEMPLATES[0]['OPTIONS'])

DATA_DIR = tmpdir.name
LOG_DIR = os.path.join(DATA_DIR, 'logs')
MEDIA_ROOT = os.path.join(DATA_DIR, 'media')
SITE_URL = 'http://example.com'

atexit.register(tmpdir.cleanup)

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

COMPRESS_ENABLED = COMPRESS_OFFLINE = False
COMPRESS_CACHE_BACKEND = 'testcache'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
INSTANCE_NAME = 'eventyay.com'

COMPRESS_PRECOMPILERS_ORIGINAL = COMPRESS_PRECOMPILERS
COMPRESS_PRECOMPILERS = ()
TEMPLATES[0]['OPTIONS']['loaders'] = (('django.template.loaders.cached.Loader', template_loaders),)

DEBUG = True
DEBUG_PROPAGATE_EXCEPTIONS = True

PRETIX_AUTH_BACKENDS = [
    'eventyay.base.auth.NativeAuthBackend',
]

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Disable celery
CELERY_ALWAYS_EAGER = True
HAS_CELERY = False
CELERY_BROKER_URL = None
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = True

# Don't use redis
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
HAS_REDIS = False
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}
DATABASE_REPLICA = 'default'


# Don't run migrations
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

    def setdefault(self, key, default=None):
        return None


if not os.environ.get('TRAVIS', '') and not os.environ.get('GITHUB_WORKFLOW', ''):
    MIGRATION_MODULES = DisableMigrations()

REST_FRAMEWORK = dict(REST_FRAMEWORK)
REST_FRAMEWORK['TEST_REQUEST_RENDERER_CLASSES'] = [
    'rest_framework.renderers.MultiPartRenderer',
    'rest_framework.renderers.JSONRenderer',
    'tests.testutils.api.UploadRenderer',
]
