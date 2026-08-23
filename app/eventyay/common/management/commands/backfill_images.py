"""Compress stored raster images that exceed a size threshold.

Run on a server after deploying the image compression pipeline to shrink
existing uploads in place and regenerate thumbnails where applicable.

Usage::

    python manage.py backfill_images
    python manage.py backfill_images --dry-run
    python manage.py backfill_images --min-size-kb 500 --model user
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django_scopes import scopes_disabled

from eventyay.base.models import Submission, User
from eventyay.common.image import invalidate_speaker_avatar_caches, is_svg_filename, recompress_image_field

logger = logging.getLogger(__name__)

IMAGE_TARGETS = {
    'user': (User, 'avatar', True),
    'submission': (Submission, 'image', False),
}


class Command(BaseCommand):
    help = 'Compress stored raster images larger than a threshold and regenerate thumbnails.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List files that would be compressed without modifying storage.',
        )
        parser.add_argument(
            '--min-size-kb',
            type=int,
            default=getattr(settings, 'IMAGE_BACKFILL_MIN_SIZE_KB', 500),
            help='Only process raster images larger than this many kilobytes.',
        )
        parser.add_argument(
            '--model',
            choices=sorted(IMAGE_TARGETS),
            action='append',
            dest='models',
            help='Limit processing to one model (user or submission). Repeatable.',
        )

    def handle(self, *args, dry_run=False, min_size_kb=500, models=None, **options):
        min_bytes = min_size_kb * 1024
        selected = models or sorted(IMAGE_TARGETS)
        stats = {'compressed': 0, 'failed': 0, 'skipped': 0, 'dry_run': 0}

        with scopes_disabled():
            for model_key in selected:
                model, field_name, generate_thumbnail = IMAGE_TARGETS[model_key]
                queryset = model.objects.exclude(**{f'{field_name}__isnull': True}).exclude(**{field_name: ''})
                for instance in queryset.iterator(chunk_size=200):
                    image = getattr(instance, field_name)
                    if not image or not image.name or is_svg_filename(image.name):
                        stats['skipped'] += 1
                        continue

                    try:
                        size = image.size
                    except Exception:
                        stats['failed'] += 1
                        logger.exception('Could not read size for %s on %s pk=%s', image.name, model.__name__, instance.pk)
                        self.stderr.write(
                            self.style.ERROR(f'FAILED size read: {model.__name__} pk={instance.pk} file={image.name}')
                        )
                        continue

                    if size <= min_bytes:
                        stats['skipped'] += 1
                        continue

                    if dry_run:
                        stats['dry_run'] += 1
                        location = getattr(image, 'path', 'remote storage')
                        self.stdout.write(
                            f'WOULD compress {model.__name__} pk={instance.pk} name={image.name} location={location} size={size / 1024:.2f} KB'
                        )
                        continue

                    if recompress_image_field(image, generate_thumbnail=generate_thumbnail):
                        stats['compressed'] += 1
                        if model is User:
                            invalidate_speaker_avatar_caches(instance)
                        try:
                            new_size = image.size
                        except Exception:
                            new_size = 'unknown'
                        location = getattr(image, 'path', 'remote storage')
                        
                        size_kb = f'{size / 1024:.2f} KB'
                        new_size_kb = f'{new_size / 1024:.2f} KB' if isinstance(new_size, int) else 'unknown'
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Compressed {model.__name__} pk={instance.pk} name={image.name} location={location} (size: {size_kb} -> {new_size_kb})'
                            )
                        )
                    else:
                        stats['failed'] += 1
                        self.stderr.write(
                            self.style.ERROR(f'FAILED compress: {model.__name__} pk={instance.pk} file={image.name}')
                        )

        self.stdout.write(
            self.style.SUCCESS(
                'Done. compressed=%(compressed)s failed=%(failed)s skipped=%(skipped)s dry_run=%(dry_run)s'
                % stats
            )
        )
