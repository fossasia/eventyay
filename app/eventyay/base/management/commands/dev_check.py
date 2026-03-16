from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.parse import urlunparse
from urllib.request import urlopen

import redis
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db.utils import OperationalError
from django.db.utils import ProgrammingError
from django.urls import reverse
from django.urls import NoReverseMatch


class Command(BaseCommand):
    help = 'Validate local development dependencies (DB, Redis, API and static files).'

    def handle(self, *args, **options):
        checks = [
            ('Database', self.check_database),
            ('Redis', self.check_redis),
            ('Django API', self.check_api),
            ('Static Files', self.check_static_files),
        ]

        self.stdout.write('Development Environment Validation')

        has_failure = False
        for name, check_fn in checks:
            ok, reason, hint = check_fn()
            if ok:
                self.stdout.write(f'{name}: PASS')
                continue

            has_failure = True
            self.stdout.write(self.style.ERROR(f'{name}: FAIL'))
            self.stdout.write(f'Reason: {reason}')
            self.stdout.write(f'Hint: {hint}')

        if has_failure:
            raise CommandError('One or more development checks failed.')

    def check_database(self):
        try:
            # Force a simple ORM query to ensure DB connectivity and model access.
            get_user_model().objects.exists()
            return True, '', ''
        except OperationalError as exc:
            return (
                False,
                str(exc),
                'Verify PostgreSQL is running and values in eventyay.local.toml are correct.',
            )
        except ProgrammingError as exc:
            return (
                False,
                str(exc),
                'Run database migrations: python manage.py migrate',
            )

    def check_redis(self):
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost/0')
        try:
            client = redis.Redis.from_url(redis_url)
            client.ping()
            return True, '', ''
        except (redis.exceptions.RedisError, ValueError) as exc:
            return (
                False,
                f'Cannot connect to {redis_url} ({exc})',
                'Make sure Redis server is running and REDIS_URL points to the right host/port.',
            )

    def check_api(self):
        url = self._build_healthcheck_url()
        try:
            with urlopen(url, timeout=3) as response:  # nosec B310
                status = response.getcode()
            if status == 200:
                return True, '', ''
            return (
                False,
                f'Health endpoint returned HTTP {status}.',
                f'Start the dev server and verify this URL: {url}',
            )
        except HTTPError as exc:
            return (
                False,
                f'Health endpoint returned HTTP {exc.code}.',
                f'Start the dev server and verify this URL: {url}',
            )
        except URLError as exc:
            return (
                False,
                f'Cannot reach {url} ({exc.reason}).',
                f'Start the dev server with: python manage.py runserver',
            )
        except TimeoutError as exc:
            return (
                False,
                str(exc),
                f'Start the dev server and verify this URL: {url}',
            )

    def _build_healthcheck_url(self) -> str:
        try:
            path = reverse('healthcheck')
        except NoReverseMatch:
            path = '/healthcheck/'

        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        parsed = urlparse(site_url)
        scheme = parsed.scheme or 'http'
        netloc = parsed.netloc or '127.0.0.1:8000'
        if ':' not in netloc:
            netloc = f'{netloc}:8000'
        return urlunparse((scheme, netloc, path, '', '', ''))

    def check_static_files(self):
        try:
            static_root = Path(settings.STATIC_ROOT)
        except (AttributeError, TypeError):
            return (
                False,
                'STATIC_ROOT is not configured.',
                'Check Django static settings before running this command.',
            )

        if static_root.exists() and static_root.is_dir():
            if any(path.is_file() for path in static_root.rglob('*')):
                return True, '', ''
            return (
                False,
                f'STATIC_ROOT is empty: {static_root}',
                'Run: python manage.py collectstatic --noinput',
            )

        if settings.DEBUG:
            static_dirs = [Path(p) for p in getattr(settings, 'STATICFILES_DIRS', ())]
            if any(directory.exists() and any(path.is_file() for path in directory.rglob('*')) for directory in static_dirs):
                return True, '', ''
            return (
                False,
                'STATIC_ROOT does not exist and no static source directories were found.',
                'Ensure STATICFILES_DIRS points to existing folders or run: python manage.py collectstatic --noinput',
            )

        return (
            False,
            f'STATIC_ROOT does not exist: {static_root}',
            'Run: python manage.py collectstatic --noinput',
        )
