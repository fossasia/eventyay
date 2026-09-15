"""
Django management command for theme management operations.

Provides utilities for initializing, validating, and managing themes.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, Organizer
from eventyay.eventyay_common.models import EventTheme, OrganizerTheme
from eventyay.eventyay_common.theme.loader import ThemeTokenLoader


class Command(BaseCommand):
    """Theme management command."""

    help = _('Manage design tokens and theme configurations')

    def add_arguments(self, parser):
        """Add command arguments."""
        subparsers = parser.add_subparsers(dest='action', help='Action to perform')

        # Initialize themes
        init_parser = subparsers.add_parser('init', help='Initialize themes for all orgs/events')
        init_parser.add_argument('--force', action='store_true', help='Overwrite existing themes')

        # Validate overrides
        validate_parser = subparsers.add_parser('validate', help='Validate theme overrides')
        validate_parser.add_argument('--organizer', help='Organizer slug')
        validate_parser.add_argument('--event', help='Event slug')

        # Reset theme
        reset_parser = subparsers.add_parser('reset', help='Reset theme to defaults')
        reset_parser.add_argument('--organizer', help='Organizer slug')
        reset_parser.add_argument('--event', help='Event slug')
        reset_parser.add_argument('--all', action='store_true', help='Reset all themes')

        # Export tokens
        export_parser = subparsers.add_parser('export', help='Export tokens to file')
        export_parser.add_argument('--output', default='tokens.json', help='Output file')
        export_parser.add_argument('--organizer', help='Organizer slug')
        export_parser.add_argument('--event', help='Event slug')

        # List themes
        list_parser = subparsers.add_parser('list', help='List all themes')
        list_parser.add_argument('--type', choices=['organizer', 'event'], help='Theme type to list')

    def handle(self, *args, **options):
        """Execute command."""
        action = options.get('action')

        if action == 'init':
            self.handle_init(**options)
        elif action == 'validate':
            self.handle_validate(**options)
        elif action == 'reset':
            self.handle_reset(**options)
        elif action == 'export':
            self.handle_export(**options)
        elif action == 'list':
            self.handle_list(**options)
        else:
            self.print_help('manage.py', 'theme')

    def handle_init(self, **options):
        """Initialize themes for all organizations and events."""
        force = options.get('force', False)

        # Initialize organizer themes
        for organizer in Organizer.objects.all():
            theme, created = OrganizerTheme.objects.get_or_create(organizer=organizer)
            status = 'created' if created else 'already exists'
            self.stdout.write(f'OrganizerTheme for {organizer.name}: {status}')

        # Initialize event themes
        for event in Event.objects.all():
            theme, created = EventTheme.objects.get_or_create(event=event)
            status = 'created' if created else 'already exists'
            self.stdout.write(f'EventTheme for {event.name}: {status}')

        self.stdout.write(self.style.SUCCESS('Theme initialization complete'))

    def handle_validate(self, **options):
        """Validate theme overrides."""
        organizer_slug = options.get('organizer')
        event_slug = options.get('event')

        try:
            if event_slug and organizer_slug:
                organizer = Organizer.objects.get(slug=organizer_slug)
                event = Event.objects.get(slug=event_slug, organizer=organizer)
                theme = EventTheme.objects.get(event=event)
                self.stdout.write(f'Validating EventTheme for {event.name}')
            elif organizer_slug:
                organizer = Organizer.objects.get(slug=organizer_slug)
                theme = OrganizerTheme.objects.get(organizer=organizer)
                self.stdout.write(f'Validating OrganizerTheme for {organizer.name}')
            else:
                raise CommandError('Provide --organizer and optionally --event')

            # Validate overrides by attempting to merge
            merged = ThemeTokenLoader.get_merged_tokens(
                base_overrides=theme.token_overrides
            )

            self.stdout.write(self.style.SUCCESS('✓ Theme validation passed'))
            self.stdout.write(f'Tokens count: {len(self._flatten(merged))}')

        except (Organizer.DoesNotExist, Event.DoesNotExist, OrganizerTheme.DoesNotExist, EventTheme.DoesNotExist) as e:
            raise CommandError(f'Theme not found: {e}')

    def handle_reset(self, **options):
        """Reset themes to defaults."""
        organizer_slug = options.get('organizer')
        event_slug = options.get('event')
        reset_all = options.get('all', False)

        if reset_all:
            count_org = OrganizerTheme.objects.update(token_overrides={})
            count_event = EventTheme.objects.update(token_overrides={})
            self.stdout.write(self.style.SUCCESS(
                f'Reset {count_org} organizer themes and {count_event} event themes'
            ))
        elif event_slug and organizer_slug:
            organizer = Organizer.objects.get(slug=organizer_slug)
            event = Event.objects.get(slug=event_slug, organizer=organizer)
            theme = EventTheme.objects.get(event=event)
            theme.clear_overrides()
            self.stdout.write(self.style.SUCCESS(f'Reset EventTheme for {event.name}'))
        elif organizer_slug:
            organizer = Organizer.objects.get(slug=organizer_slug)
            theme = OrganizerTheme.objects.get(organizer=organizer)
            theme.clear_overrides()
            self.stdout.write(self.style.SUCCESS(f'Reset OrganizerTheme for {organizer.name}'))
        else:
            raise CommandError('Provide --all, or --organizer with optionally --event')

    def handle_export(self, **options):
        """Export tokens to file."""
        output_file = options.get('output', 'tokens.json')
        organizer_slug = options.get('organizer')
        event_slug = options.get('event')

        try:
            if event_slug and organizer_slug:
                organizer = Organizer.objects.get(slug=organizer_slug)
                event = Event.objects.get(slug=event_slug, organizer=organizer)
                theme = EventTheme.objects.get(event=event)
                tokens = theme.get_effective_tokens()
                name = f'EventTheme: {event.name}'
            elif organizer_slug:
                organizer = Organizer.objects.get(slug=organizer_slug)
                theme = OrganizerTheme.objects.get(organizer=organizer)
                tokens = ThemeTokenLoader.get_merged_tokens(base_overrides=theme.token_overrides)
                name = f'OrganizerTheme: {organizer.name}'
            else:
                # Export base tokens
                tokens = ThemeTokenLoader.load_base_tokens()
                name = 'Base Tokens'

            import json
            with open(output_file, 'w') as f:
                json.dump({'name': name, 'tokens': tokens}, f, indent=2)

            self.stdout.write(self.style.SUCCESS(f'Tokens exported to {output_file}'))

        except (Organizer.DoesNotExist, Event.DoesNotExist, OrganizerTheme.DoesNotExist, EventTheme.DoesNotExist) as e:
            raise CommandError(f'Object not found: {e}')

    def handle_list(self, **options):
        """List all themes."""
        theme_type = options.get('type')

        if theme_type in (None, 'organizer'):
            self.stdout.write(self.style.HTTP_INFO('=== Organizer Themes ==='))
            for theme in OrganizerTheme.objects.select_related('organizer'):
                status = '✓' if theme.is_active else '✗'
                colors = theme.get_primary_color() or 'not set'
                self.stdout.write(f'{status} {theme.organizer.name}: primary={colors}')

        if theme_type in (None, 'event'):
            self.stdout.write(self.style.HTTP_INFO('\n=== Event Themes ==='))
            for theme in EventTheme.objects.select_related('event', 'event__organizer'):
                status = '✓' if theme.is_active else '✗'
                colors = theme.get_primary_color() or 'not set'
                self.stdout.write(
                    f'{status} {theme.event.organizer.name} / {theme.event.name}: primary={colors}'
                )

    @staticmethod
    def _flatten(d, parent_key='', sep='.'):
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f'{parent_key}{sep}{k}' if parent_key else k
            if isinstance(v, dict):
                items.extend(Command._flatten(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
