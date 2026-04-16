from django.core.management.base import BaseCommand

from eventyay.base.schedule_cache import warm_event_build_data_caches, warm_video_spa_pages


class Command(BaseCommand):
    help = 'Warm released schedule build_data cache and optionally video SPA HTML cache.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=150,
            help='Maximum number of events with a released current schedule to warm.',
        )
        parser.add_argument(
            '--video',
            action='store_true',
            help='Also warm video SPA HTML (anonymous /{org}/{event}/video/ response).',
        )

    def handle(self, *args, limit: int, video: bool, **options):
        n_sched = warm_event_build_data_caches(max_events=limit)
        self.stdout.write(self.style.SUCCESS('Warmed build_data for %s events' % n_sched))
        if video:
            n_vid = warm_video_spa_pages(max_events=min(limit, 80))
            self.stdout.write(self.style.SUCCESS('Warmed video SPA HTML for %s events' % n_vid))
