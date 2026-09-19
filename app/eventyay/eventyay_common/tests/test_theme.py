"""
Tests for the token-based theming system.

Verifies token loading, merging, and model functionality.
"""

from django.test import TestCase

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


class EventThemeModelTestCase(TestCase):
    """Test EventTheme model functionality."""

    def setUp(self):
        """Set up test fixtures."""
        from datetime import timedelta

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
        OrganizerTheme.objects.create(
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
        OrganizerTheme.objects.create(
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


class ThemeFormsTestCase(TestCase):
    """Test theme forms and validation."""

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone
        self.organizer = Organizer.objects.create(name='Form Org', slug='form-org')
        self.event = Event.objects.create(
            name='Form Event',
            slug='form-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timedelta(days=1),
        )

    def test_event_theme_form_valid(self):
        from eventyay.orga.forms.theme import EventThemeForm
        form_data = {
            'color_mode': 'dark',
            'primary_color': '#EB2188',
            'secondary_color': '#3B82F6',
            'inherit_organizer_theme': True,
            'is_active': True,
            'custom_css': '.btn { color: red; }',
            'description': 'Test description',
        }
        form = EventThemeForm(data=form_data)
        self.assertTrue(form.is_valid())
        theme = form.save(commit=False)
        theme.event = self.event
        theme.save()
        self.assertEqual(theme.color_mode, 'dark')
        self.assertEqual(theme.token_overrides['colors']['primary'], '#EB2188')
        self.assertEqual(theme.token_overrides['colors']['secondary'], '#3B82F6')

    def test_event_theme_form_unbalanced_css(self):
        from eventyay.orga.forms.theme import EventThemeForm
        form_data = {
            'color_mode': 'light',
            'custom_css': '.btn { color: red;',
        }
        form = EventThemeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('custom_css', form.errors)

    def test_token_import_form_valid(self):
        import json

        from django.core.files.uploadedfile import SimpleUploadedFile

        from eventyay.orga.forms.theme import TokenImportForm
        valid_json = json.dumps({'colors': {'primary': '#123456'}}).encode('utf-8')
        file = SimpleUploadedFile('theme.json', valid_json, content_type='application/json')
        form = TokenImportForm(data={'override_existing': True}, files={'json_file': file})
        self.assertTrue(form.is_valid())

    def test_token_import_form_invalid_json(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from eventyay.orga.forms.theme import TokenImportForm
        invalid_json = b'{not valid json'
        file = SimpleUploadedFile('theme.json', invalid_json, content_type='application/json')
        form = TokenImportForm(data={'override_existing': True}, files={'json_file': file})
        self.assertFalse(form.is_valid())
        self.assertIn('json_file', form.errors)


class ThemeAPITestCase(TestCase):
    """Test Theme API viewsets."""

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone
        self.organizer = Organizer.objects.create(name='API Org', slug='api-org')
        self.event = Event.objects.create(
            name='API Event',
            slug='api-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timedelta(days=1),
        )
        self.user = User.objects.create(email='test@example.com')

    def test_organizer_theme_api_retrieve(self):
        from rest_framework.test import APIRequestFactory

        from eventyay.api.views.theme import OrganizerThemeViewSet
        factory = APIRequestFactory()
        view = OrganizerThemeViewSet.as_view({'get': 'retrieve'})
        request = factory.get(f'/api/v1/organizers/{self.organizer.slug}/themes/')
        request.user = self.user
        response = view(request, organizer_slug=self.organizer.slug)
        self.assertEqual(response.status_code, 200)
        self.assertIn('tokens', response.data)

    def test_event_theme_api_retrieve(self):
        from rest_framework.test import APIRequestFactory

        from eventyay.api.views.theme import EventThemeViewSet
        factory = APIRequestFactory()
        view = EventThemeViewSet.as_view({'get': 'retrieve'})
        request = factory.get(f'/api/v1/organizers/{self.organizer.slug}/events/{self.event.slug}/theme/')
        request.user = self.user
        response = view(request, organizer_slug=self.organizer.slug, event_slug=self.event.slug)
        self.assertEqual(response.status_code, 200)
        self.assertIn('tokens', response.data)

    def test_event_theme_api_export(self):
        from rest_framework.test import APIRequestFactory

        from eventyay.api.views.theme import EventThemeViewSet
        factory = APIRequestFactory()
        view = EventThemeViewSet.as_view({'post': 'export'})
        request = factory.post(f'/api/v1/organizers/{self.organizer.slug}/events/{self.event.slug}/theme/export/')
        request.user = self.user
        response = view(request, organizer_slug=self.organizer.slug, event_slug=self.event.slug)
        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.data)
        self.assertIn('colorMode', response.data)


class ThemeContextTestCase(TestCase):
    """Test theme context processor injection."""

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone
        self.organizer = Organizer.objects.create(name='Ctx Org', slug='ctx-org')
        self.event = Event.objects.create(
            name='Ctx Event',
            slug='ctx-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timedelta(days=1),
        )

    def test_event_theme_in_context(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from django_scopes import scope

        from eventyay.presale.context import _default_context
        EventTheme.objects.create(
            event=self.event,
            color_mode='dark',
            custom_css='.custom { color: red; }',
            token_overrides={'colors': {'primary': '#112233'}},
        )
        factory = RequestFactory()
        request = factory.get('/')
        request.user = AnonymousUser()
        request.event = self.event
        request.organizer = self.organizer
        request.resolver_match = None

        with scope(event=self.event):
            ctx = _default_context(request)
        self.assertIn('event_theme', ctx)
        self.assertIn('#112233', ctx['event_theme_tokens'])
        self.assertEqual(ctx['event_theme_color_mode'], 'dark')
        self.assertEqual(ctx['event_theme_custom_css'], '.custom { color: red; }')

