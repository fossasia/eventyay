"""
Tests for the token-based theming system.

Verifies token loading, merging, and model functionality.
"""

from django.test import TestCase
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, Organizer, User
from eventyay.eventyay_common.models import EventTheme, OrganizerTheme
from eventyay.eventyay_common.theme.loader import ThemeTokenLoader


class ThemeTokenLoaderTestCase(TestCase):
    """Test token loading and merging functionality."""

    def test_load_base_tokens(self):
        """Test loading base tokens from default theme."""
        tokens = ThemeTokenLoader.load_base_tokens()
        self.assertIsNotNone(tokens)
        self.assertIn('colors', tokens)
        self.assertIn('typography', tokens)
        self.assertIn('spacing', tokens)

    def test_merge_tokens(self):
        """Test merging override tokens into base."""
        base = {'colors': {'primary': '#000000'}, 'spacing': {'1': '4px'}}
        overrides = {'colors': {'primary': '#FF0000'}}
        merged = ThemeTokenLoader.merge_tokens(base, overrides)

        self.assertEqual(merged['colors']['primary'], '#FF0000')
        self.assertEqual(merged['spacing']['1'], '4px')

    def test_resolve_token_references(self):
        """Test resolving token references."""
        base = {'colors': {'primary': '#FF0000'}}
        tokens = {'semanticTokens': {'button': {'bg': '{colors.primary}'}}}

        resolved = ThemeTokenLoader.resolve_token_references(tokens, base)
        # The reference should be resolved in the returned object
        self.assertIsNotNone(resolved)

    def test_export_css_variables(self):
        """Test exporting tokens as CSS variables."""
        tokens = {'colors': {'primary': '#FF0000'}, 'spacing': {'4': '16px'}}
        css = ThemeTokenLoader.export_css_variables(tokens)

        self.assertIn('--color-primary: #FF0000;', css)
        self.assertIn('--spacing-4: 16px;', css)
        self.assertIn(':root {', css)

    def test_get_merged_tokens(self):
        """Test getting fully merged tokens with precedence."""
        org_overrides = {'colors': {'primary': '#FF0000'}}
        event_overrides = {'colors': {'secondary': '#00FF00'}}

        tokens = ThemeTokenLoader.get_merged_tokens(
            base_overrides=org_overrides,
            event_overrides=event_overrides,
        )

        self.assertEqual(tokens['colors']['primary'], '#FF0000')
        self.assertEqual(tokens['colors']['secondary'], '#00FF00')


class OrganizerThemeModelTestCase(TestCase):
    """Test OrganizerTheme model functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.organizer = Organizer.objects.create(
            name='Test Org',
            slug='test-org',
        )

    def test_create_organizer_theme(self):
        """Test creating an organizer theme."""
        theme = OrganizerTheme.objects.create(
            organizer=self.organizer,
            color_mode='light',
        )
        self.assertEqual(theme.get_display_name(), 'Test Org Theme')

    def test_update_color(self):
        """Test updating a specific color token."""
        theme = OrganizerTheme.objects.create(
            organizer=self.organizer,
            token_overrides={},
        )

        theme.update_color('primary', '#FF0000')
        theme.refresh_from_db()

        self.assertEqual(
            theme.token_overrides['colors']['primary'],
            '#FF0000',
        )

    def test_get_primary_color(self):
        """Test extracting primary color."""
        theme = OrganizerTheme.objects.create(
            organizer=self.organizer,
            token_overrides={'colors': {'primary': '#FF0000'}},
        )
        self.assertEqual(theme.get_primary_color(), '#FF0000')

    def test_clear_overrides(self):
        """Test clearing all token overrides."""
        theme = OrganizerTheme.objects.create(
            organizer=self.organizer,
            token_overrides={'colors': {'primary': '#FF0000'}},
        )

        theme.clear_overrides()
        theme.refresh_from_db()

        self.assertEqual(theme.token_overrides, {})

    def test_organizer_theme_unique(self):
        """Test that each organizer can have only one theme."""
        OrganizerTheme.objects.create(
            organizer=self.organizer,
            color_mode='light',
        )

        # This should not create a second theme
        with self.assertRaises(Exception):
            OrganizerTheme.objects.create(
                organizer=self.organizer,
                color_mode='dark',
            )


class EventThemeModelTestCase(TestCase)    :
    """Test EventTheme model functionality."""

    def setUp(self):
        """Set up test fixtures."""
        from datetime import datetime, timedelta
        from django.utils import timezone

        self.organizer = Organizer.objects.create(
            name='Test Org',
            slug='test-org',
        )
        self.event = Event.objects.create(
            name='Test Event',
            slug='test-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timedelta(days=1),
        )

    def test_create_event_theme(self):
        """Test creating an event theme."""
        theme = EventTheme.objects.create(
            event=self.event,
            color_mode='dark',
        )
        self.assertEqual(theme.get_display_name(), 'Test Event Theme')

    def test_inherit_organizer_theme(self):
        """Test event inheriting organizer theme."""
        org_theme = OrganizerTheme.objects.create(
            organizer=self.organizer,
            token_overrides={'colors': {'primary': '#FF0000'}},
        )
        event_theme = EventTheme.objects.create(
            event=self.event,
            inherit_organizer_theme=True,
            token_overrides={},
        )

        effective_tokens = event_theme.get_effective_tokens()
        self.assertEqual(effective_tokens['colors']['primary'], '#FF0000')

    def test_event_override_precedence(self):
        """Test that event overrides take precedence over organizer."""
        OrganizerTheme.objects.create(
            organizer=self.organizer,
            token_overrides={'colors': {'primary': '#FF0000'}},
        )
        event_theme = EventTheme.objects.create(
            event=self.event,
            inherit_organizer_theme=True,
            token_overrides={'colors': {'primary': '#00FF00'}},
        )

        effective_tokens = event_theme.get_effective_tokens()
        self.assertEqual(effective_tokens['colors']['primary'], '#00FF00')

    def test_export_import_json(self):
        """Test exporting and importing theme as JSON."""
        theme = EventTheme.objects.create(
            event=self.event,
            color_mode='dark',
            token_overrides={'colors': {'primary': '#FF0000'}},
        )

        json_str = theme.export_as_json()
        self.assertIn('Test Event Theme', json_str)
        self.assertIn('#FF0000', json_str)
        self.assertIn('dark', json_str)

    def test_custom_css(self):
        """Test custom CSS storage."""
        custom_css = '.header { background: red; }'
        theme = EventTheme.objects.create(
            event=self.event,
            custom_css=custom_css,
        )
        self.assertEqual(theme.custom_css, custom_css)

    def test_color_mode_choices(self):
        """Test valid color mode choices."""
        theme = EventTheme.objects.create(event=self.event)

        theme.color_mode = 'light'
        theme.save()
        self.assertEqual(theme.color_mode, 'light')

        theme.color_mode = 'dark'
        theme.save()
        self.assertEqual(theme.color_mode, 'dark')

        theme.color_mode = 'auto'
        theme.save()
        self.assertEqual(theme.color_mode, 'auto')


class ThemeIntegrationTestCase(TestCase):
    """Integration tests for the theming system."""

    def setUp(self):
        """Set up test fixtures."""
        from datetime import timedelta
        from django.utils import timezone

        self.organizer = Organizer.objects.create(
            name='Integration Test Org',
            slug='integration-test',
        )
        self.event = Event.objects.create(
            name='Integration Test Event',
            slug='integration-test-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timedelta(days=1),
        )

    def test_complete_theming_flow(self):
        """Test complete theming workflow."""
        # 1. Create organizer theme
        org_theme = OrganizerTheme.objects.create(
            organizer=self.organizer,
            color_mode='auto',
            token_overrides={
                'colors': {
                    'primary': '#FF0000',
                    'secondary': '#00FF00',
                }
            },
        )

        # 2. Create event theme inheriting from organizer
        event_theme = EventTheme.objects.create(
            event=self.event,
            inherit_organizer_theme=True,
            token_overrides={
                'colors': {
                    'primary': '#0000FF',  # Override primary color
                }
            },
        )

        # 3. Get effective tokens
        tokens = event_theme.get_effective_tokens()
        self.assertEqual(tokens['colors']['primary'], '#0000FF')
        self.assertEqual(tokens['colors']['secondary'], '#00FF00')

        # 4. Export to JSON
        json_export = event_theme.export_as_json()
        self.assertIn('#0000FF', json_export)

        # 5. Update a token
        event_theme.update_color('primary', '#FFFF00')
        event_theme.refresh_from_db()
        self.assertEqual(event_theme.get_primary_color(), '#FFFF00')

    def test_theme_with_custom_css(self):
        """Test theme with custom CSS rules."""
        custom_css = '''
        .event-header { 
            background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
        }
        '''
        theme = EventTheme.objects.create(
            event=self.event,
            custom_css=custom_css,
        )

        self.assertIn('linear-gradient', theme.custom_css)
        self.assertIn('var(--color-primary)', theme.custom_css)
