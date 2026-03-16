from __future__ import annotations

from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

import redis
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError


class Command(BaseCommand):
    help = 'Validate local development dependencies (DB, Redis, API and static files).'

    def handle(self, *args, **options):
        checks = [
            ('Database', self.check_database),
            ('Redis', self.check_redis),
            ('Django API', self.check_api),
            ('Static Files', self.check_static_files),
        ]

        self.stdout.write('Development Environment Validation\n')

        has_failure = False
        for name, check_fn in checks:
            ok, reason, hint = check_fn()
            if ok:
                self.stdout.write(f'{name}: PASS')
                continue

            has_failure = True
            self.stdout.write(self.style.ERROR(f'{name}: FAIL'))
            self.stdout.write(f'Reason: {reason}')
            self.stdout.write(f'Hint: {hint}\n')

        if has_failure:
            raise CommandError('One or more development checks failed.')

    def check_database(self):
        try:
            # Force a simple ORM query to ensure DB connectivity and model access.
            get_user_model().objects.exists()
            return True, '', ''
        except Exception as exc:
            return (
                False,
                str(exc),
                'Verify PostgreSQL is running and values in eventyay.local.toml are correct.',
            )

    def check_redis(self):
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost/0')
        try:
            client = redis.Redis.from_url(redis_url)
            client.ping()
            return True, '', ''
        except Exception as exc:
            return (
                False,
                f'Cannot connect to {redis_url} ({exc})',
                'Make sure Redis server is running and REDIS_URL points to the right host/port.',
            )

    def check_api(self):
        url = 'http://127.0.0.1:8000/healthcheck/'
        try:
            with urlopen(url, timeout=3) as response:  # nosec B310
                status = response.getcode()
            if status == 200:
                return True, '', ''
            return (
                False,
                f'Health endpoint returned HTTP {status}.',
                'Start the dev server with: python manage.py runserver',
            )
        except HTTPError as exc:
            return (
                False,
                f'Health endpoint returned HTTP {exc.code}.',
                'Start the dev server with: python manage.py runserver',
            )
        except URLError as exc:
            return (
                False,
                f'Cannot reach {url} ({exc.reason}).',
                'Start the dev server with: python manage.py runserver',
            )
        except Exception as exc:
            return (
                False,
                str(exc),
                'Start the dev server with: python manage.py runserver',
            )

    def check_static_files(self):
        try:
            static_root = Path(settings.STATIC_ROOT)
        except Exception:
            return (
                False,
                'STATIC_ROOT is not configured.',
                'Check Django static settings before running this command.',
            )

        if not static_root.exists():
            return (
                False,
                f'STATIC_ROOT does not exist: {static_root}',
                'Run: python manage.py collectstatic --noinput',
            )

        if not any(static_root.rglob('*')):
            return (
                False,
                f'STATIC_ROOT is empty: {static_root}',
                'Run: python manage.py collectstatic --noinput',
            )

        return True, '', ''
