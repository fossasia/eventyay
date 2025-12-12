"""
Dev-specific settings wrapper.

This file imports the main `next_settings` and applies a small set of overrides
so the same codebase can be deployed for the `dev` branch without duplicating
the full settings file.

Note: The canonical settings for the next (production preview) remain in
`next_settings.py`. The `dev` branch should include this file and set
`DJANGO_SETTINGS_MODULE=eventyay.config.dev_settings` in the deployment
environment, or the deployment tooling should set
`EVY_RUNNING_ENVIRONMENT` and provide `eventyay.dev.toml`.
"""

from eventyay.config.next_settings import *  # noqa: F401,F403

# Override host/CSRF trusted origins for the dev environment.
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:1337',
    'http://dev.eventyay.com:1337',
    'https://dev.eventyay.com',
]

# If the `conf` object exists and has site_url configured from TOML, the
# deployed environment will normally set that via `eventyay.dev.toml`. However
# set a sensible default here, so running the code locally still works.
try:
    # If conf.site_url is present, respect it. Otherwise, set SITE_URL to dev.
    SITE_URL = str(conf.site_url) if hasattr(conf, 'site_url') else 'https://dev.eventyay.com'
except Exception:
    SITE_URL = 'https://dev.eventyay.com'

from urllib.parse import urlparse
SITE_NETLOC = urlparse(SITE_URL).netloc
