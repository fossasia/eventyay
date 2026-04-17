import os

from tests.testutils import settings as testutils_settings
from tests.testutils.settings import *  # NOQA


TEST_DIR = os.path.dirname(__file__)

TEMPLATES[0]['DIRS'].append(os.path.join(TEST_DIR, 'templates'))  # NOQA

INSTALLED_APPS = list(testutils_settings.INSTALLED_APPS)
INSTALLED_APPS.append('tests.tickets.testdummy')  # NOQA

PRETIX_AUTH_BACKENDS = [
    'eventyay.base.auth.NativeAuthBackend',
    'tests.tickets.testdummy.auth.TestFormAuthBackend',
    'tests.tickets.testdummy.auth.TestRequestAuthBackend',
]

BASE_PATH = ''

FORCE_SCRIPT_NAME = BASE_PATH

for a in testutils_settings.PLUGINS:
    INSTALLED_APPS.remove(a)
