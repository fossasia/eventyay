import time
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand
from django.dispatch.dispatcher import NO_RECEIVERS

from eventyay.base.signals import periodic_task as base_periodic_task
from eventyay.common.signals import periodic_task as common_periodic_task
from eventyay.helpers.periodic import SKIPPED

_PERIODIC_SIGNALS = (
    base_periodic_task,
    common_periodic_task,
)


class Command(BaseCommand):
    help = 'Run periodic tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tasks',
            action='store',
            type=str,
            help='Only execute the tasks with this name (dotted path, comma separation)',
        )
        parser.add_argument(
            '--exclude',
            action='store',
            type=str,
            help='Exclude the tasks with this name (dotted path, comma separation)',
        )

    def handle(self, *args, **options):
        verbosity = int(options['verbosity'])

        has_any = any(
            sig.receivers and sig.sender_receivers_cache.get(self) is not NO_RECEIVERS
            for sig in _PERIODIC_SIGNALS
        )
        if not has_any:
            return

        for periodic_task in _PERIODIC_SIGNALS:
            if not periodic_task.receivers or periodic_task.sender_receivers_cache.get(self) is NO_RECEIVERS:
                continue

            for receiver in periodic_task._live_receivers(self):
                name = f'{receiver.__module__}.{receiver.__name__}'
                if options.get('tasks'):
                    if name not in options.get('tasks').split(','):
                        continue
                if options.get('exclude'):
                    if name in options.get('exclude').split(','):
                        continue

                if verbosity > 1:
                    self.stdout.write(f'INFO Running {name}…')
                t0 = time.time()
                try:
                    r = receiver(signal=periodic_task, sender=self)
                except KeyboardInterrupt:
                    raise
                except Exception as err:
                    if settings.SENTRY_ENABLED:
                        from sentry_sdk import capture_exception

                        capture_exception(err)
                    self.stdout.write(self.style.ERROR('ERROR runperiodic %s\n' % err))
                    if not settings.SENTRY_ENABLED:
                        traceback.print_exc()
                else:
                    if options.get('verbosity') > 1:
                        if r is SKIPPED:
                            self.stdout.write(self.style.SUCCESS(f'INFO Skipped {name}'))
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'INFO Completed {name} in {round(time.time() - t0, 3)}s'
                                )
                            )
