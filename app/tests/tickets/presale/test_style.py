import datetime
import os.path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer
from eventyay.base.settings import validate_event_settings, validate_organizer_settings
from eventyay.eventyay_common.forms.event import EventCommonSettingsForm
from eventyay.presale.style import compile_scss, regenerate_css, regenerate_organizer_css


class StyleTest(TestCase):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.orga = Organizer.objects.create(name='CCC', slug='ccc')
        self.event = Event.objects.create(
            organizer=self.orga,
            name='30C3',
            slug='30c3',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.UTC),
            live=True,
        )

    def test_organizer_generate_css_for_inherited_events(self):
        self.orga.settings.primary_color = '#33c33c'
        regenerate_organizer_css.apply(args=(self.orga.pk,))
        self.orga.settings.flush()
        assert self.orga.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.orga.settings.presale_css_file)) as c:
            assert '#33c33c' in c.read()

        self.event.settings.flush()
        assert self.event.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.event.settings.presale_css_file)) as c:
            assert '#33c33c' in c.read()

    def test_organizer_generate_css_only_for_inherited_events(self):
        self.orga.settings.primary_color = '#33c33c'
        self.event.settings.primary_color = '#34c34c'
        regenerate_organizer_css.apply(args=(self.orga.pk,))
        self.orga.settings.flush()
        assert self.orga.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.orga.settings.presale_css_file)) as c:
            assert '#33c33c' in c.read()

        self.event.settings.flush()
        assert self.event.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.event.settings.presale_css_file)) as c:
            assert '#34c34c' not in c.read()
            assert '#33c33c' not in c.read()

    def test_event_generate_css_primary_font(self):
        self.event.settings.primary_font = 'Georgia'
        regenerate_css.apply(args=(self.event.pk,))
        self.event.settings.flush()
        assert self.event.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.event.settings.presale_css_file)) as c:
            content = c.read()
            assert 'Georgia' in content

    def test_organizer_generate_css_primary_font_inherited(self):
        self.orga.settings.primary_font = 'Georgia'
        regenerate_organizer_css.apply(args=(self.orga.pk,))
        self.orga.settings.flush()
        self.event.settings.flush()
        assert self.event.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.event.settings.presale_css_file)) as c:
            content = c.read()
            assert 'Georgia' in content

    def test_validate_event_settings_primary_font(self):
        # Valid system font
        validate_event_settings(self.event, {'primary_font': 'Georgia'})

        # Invalid font
        with self.assertRaises(ValidationError):
            validate_event_settings(self.event, {'primary_font': 'NonExistentFont'})

    def test_validate_organizer_settings_primary_font(self):
        # Valid system font
        validate_organizer_settings(self.orga, {'primary_font': 'Georgia'})

        # Invalid font
        with self.assertRaises(ValidationError):
            validate_organizer_settings(self.orga, {'primary_font': 'NonExistentFont'})

    def test_event_font_form_inheritance(self):
        # 1. Set organizer font to Georgia
        self.orga.settings.primary_font = 'Georgia'

        # 2. Instantiate form and check that empty string is in choices and represents the default option
        form = EventCommonSettingsForm(obj=self.event)
        choices = dict(form.fields['primary_font'].choices)
        self.assertIn('', choices)
        self.assertIn('Georgia', choices[''])

        # 3. Save the form with empty string '' (representing Inherit)
        form = EventCommonSettingsForm(
            data={'timezone': 'UTC', 'locale': 'en', 'locales': ['en'], 'primary_font': ''},
            obj=self.event
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        # 4. Check that primary_font is NOT in the database cache for the event
        self.assertNotIn('primary_font', self.event.settings._cache())
        # 5. Check that settings.get() retrieves the organizer's font
        self.assertEqual(self.event.settings.get('primary_font'), 'Georgia')

    def test_event_css_view_with_font(self):
        self.event.settings.primary_font = 'Georgia'
        self.event.settings.primary_color = '#123456'
        response = self.client.get(
            reverse('agenda:event.css', kwargs={
                'organizer': self.orga.slug,
                'event': self.event.slug
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/css')
        content = response.content.decode()
        self.assertIn('--font-family: Georgia', content)
        self.assertIn('--color-primary: #123456', content)

    def test_organizer_compile_scss_emits_header_background_color(self):
        self.orga.settings.header_background_color = '#a1b2c3'
        css, _ = compile_scss(self.orga)
        assert '--color-header-background' in css
        assert '#a1b2c3' in css

    def test_organizer_compile_scss_emits_primary_color_as_css_var(self):
        self.orga.settings.primary_color = '#a1b2c3'
        css, _ = compile_scss(self.orga)
        assert '--color-primary' in css
        assert '#a1b2c3' in css

    def test_organizer_compile_scss_emits_theme_colors_as_css_vars(self):
        self.orga.settings.theme_color_success = '#129901'
        self.orga.settings.theme_color_danger = '#c10001'
        self.orga.settings.theme_color_background = '#e1e2e3'
        css, _ = compile_scss(self.orga)
        assert '--color-success' in css
        assert '#129901' in css
        assert '--color-danger' in css
        assert '#c10001' in css
        assert '--color-bg' in css
        assert '#e1e2e3' in css

    def test_organizer_compile_scss_emits_header_text_color(self):
        self.orga.settings.header_text_color = '#121314'
        css, _ = compile_scss(self.orga)
        assert '--color-header-text' in css
        assert '#121314' in css

    def test_organizer_compile_scss_emits_navigation_text_color(self):
        self.orga.settings.navigation_text_color = '#232425'
        css, _ = compile_scss(self.orga)
        assert '--color-header-navigation' in css
        assert '#232425' in css

    def test_organizer_compile_scss_emits_menu_text_scroll_over_color(self):
        self.orga.settings.menu_text_scroll_over_color = '#343536'
        css, _ = compile_scss(self.orga)
        assert '--color-header-navigation-hover' in css
        assert '#343536' in css

    def test_organizer_compile_scss_emits_video_colors(self):
        self.orga.settings.video_navigation_background_color = '#454647'
        self.orga.settings.video_sidebar_text_color = '#565758'
        self.orga.settings.video_sidebar_hover_color = '#676869'
        css, _ = compile_scss(self.orga)
        assert '--color-video-nav-background' in css
        assert '#454647' in css
        assert '--color-video-sidebar-text' in css
        assert '#565758' in css
        assert '--color-video-sidebar-hover' in css
        assert '#676869' in css

    def test_organizer_compile_scss_no_custom_props_when_unset(self):
        css, _ = compile_scss(self.orga)
        assert '--color-header-background' not in css
        assert '--color-header-text' not in css
        assert '--color-header-navigation:' not in css
        assert '--color-header-navigation-hover' not in css

    def test_organizer_regenerate_css_applies_header_colors_to_organizer_file(self):
        self.orga.settings.header_background_color = '#a1b2c3'
        self.orga.settings.navigation_text_color = '#d1e2f3'
        regenerate_organizer_css.apply(args=(self.orga.pk,))
        self.orga.settings.flush()
        assert self.orga.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.orga.settings.presale_css_file)) as c:
            content = c.read()
            assert '--color-header-background' in content
            assert '#a1b2c3' in content
            assert '--color-header-navigation' in content
            assert '#d1e2f3' in content

    def test_event_inherits_header_colors_from_organizer(self):
        self.orga.settings.header_background_color = '#a1b2c3'
        self.orga.settings.navigation_text_color = '#d1e2f3'
        regenerate_organizer_css.apply(args=(self.orga.pk,))
        regenerate_css.apply(args=(self.event.pk,))
        self.event.refresh_from_db()
        self.event.settings.flush()
        self.orga.settings.flush()
        assert self.event.settings.presale_css_file or self.orga.settings.presale_css_file
        css_file = self.event.settings.presale_css_file or self.orga.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, css_file)) as c:
            content = c.read()
            assert '--color-header-background' in content
            assert '#a1b2c3' in content
            assert '--color-header-navigation' in content
            assert '#d1e2f3' in content

    def test_event_own_header_color_overrides_organizer(self):
        self.orga.settings.header_background_color = '#a1b2c3'
        self.event.settings.header_background_color = '#d1e2f3'
        regenerate_css.apply(args=(self.event.pk,))
        self.event.refresh_from_db()
        self.event.settings.flush()
        assert self.event.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.event.settings.presale_css_file)) as c:
            content = c.read()
            assert '--color-header-background' in content
            assert '#d1e2f3' in content
            assert '#a1b2c3' not in content

    def test_existing_scss_variables_still_emitted(self):
        self.orga.settings.primary_color = '#33c33c'
        self.orga.settings.theme_color_success = '#009901'
        self.orga.settings.theme_color_danger = '#ff0001'
        css, _ = compile_scss(self.orga)
        assert '#33c33c' in css
        assert '#009901' in css
        assert '#ff0001' in css

    def test_event_css_view_with_font_target_orga(self):
        self.event.settings.primary_font = 'Georgia'
        self.event.settings.primary_color = '#123456'
        response = self.client.get(
            reverse('agenda:event.css', kwargs={
                'organizer': self.orga.slug,
                'event': self.event.slug
            }) + '?target=orga'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/css')
        content = response.content.decode()
        self.assertNotIn('--font-family', content)
        self.assertIn('--color-primary-event: #123456', content)
