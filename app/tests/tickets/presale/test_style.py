import datetime
import os.path

from django.conf import settings
from django.test import TestCase
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer
from eventyay.presale.style import regenerate_organizer_css


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
        from eventyay.presale.style import regenerate_css
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
        from django.core.exceptions import ValidationError

        from eventyay.base.settings import validate_event_settings

        # Valid system font
        validate_event_settings(self.event, {'primary_font': 'Georgia'})

        # Invalid font
        with self.assertRaises(ValidationError):
            validate_event_settings(self.event, {'primary_font': 'NonExistentFont'})

    def test_validate_organizer_settings_primary_font(self):
        from django.core.exceptions import ValidationError

        from eventyay.base.settings import validate_organizer_settings

        # Valid system font
        validate_organizer_settings(self.orga, {'primary_font': 'Georgia'})

        # Invalid font
        with self.assertRaises(ValidationError):
            validate_organizer_settings(self.orga, {'primary_font': 'NonExistentFont'})

    def test_event_font_form_inheritance(self):
        from eventyay.eventyay_common.forms.event import EventCommonSettingsForm

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
        from django.urls import reverse
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
        from eventyay.presale.style import compile_scss
        self.orga.settings.header_background_color = '#aabbcc'
        css, _ = compile_scss(self.orga)
        assert '--color-header-background: #aabbcc' in css

    def test_organizer_compile_scss_emits_primary_color_as_css_var(self):
        from eventyay.presale.style import compile_scss
        self.orga.settings.primary_color = '#aa1122'
        css, _ = compile_scss(self.orga)
        assert '#aa1122' in css
        assert '--color-primary: #aa1122' in css

    def test_organizer_compile_scss_emits_theme_colors_as_css_vars(self):
        from eventyay.presale.style import compile_scss
        self.orga.settings.theme_color_success = '#009900'
        self.orga.settings.theme_color_danger = '#cc0000'
        self.orga.settings.theme_color_background = '#eeeeee'
        css, _ = compile_scss(self.orga)
        assert '--color-success: #009900' in css
        assert '--color-danger: #cc0000' in css
        assert '--color-bg: #eeeeee' in css

    def test_organizer_compile_scss_emits_header_text_color(self):
        from eventyay.presale.style import compile_scss
        self.orga.settings.header_text_color = '#111111'
        css, _ = compile_scss(self.orga)
        assert '--color-header-text: #111111' in css

    def test_organizer_compile_scss_emits_navigation_text_color(self):
        from eventyay.presale.style import compile_scss
        self.orga.settings.navigation_text_color = '#222222'
        css, _ = compile_scss(self.orga)
        assert '--color-header-navigation: #222222' in css

    def test_organizer_compile_scss_emits_menu_text_scroll_over_color(self):
        from eventyay.presale.style import compile_scss
        self.orga.settings.menu_text_scroll_over_color = '#333333'
        css, _ = compile_scss(self.orga)
        assert '--color-header-navigation-hover: #333333' in css

    def test_organizer_compile_scss_emits_video_colors(self):
        from eventyay.presale.style import compile_scss
        self.orga.settings.video_navigation_background_color = '#444444'
        self.orga.settings.video_sidebar_text_color = '#555555'
        self.orga.settings.video_sidebar_hover_color = '#666666'
        css, _ = compile_scss(self.orga)
        assert '--color-video-nav-background: #444444' in css
        assert '--color-video-sidebar-text: #555555' in css
        assert '--color-video-sidebar-hover: #666666' in css

    def test_organizer_compile_scss_no_custom_props_when_unset(self):
        from eventyay.presale.style import compile_scss
        css, _ = compile_scss(self.orga)
        assert '--color-header-background' not in css
        assert '--color-header-text' not in css
        assert '--color-header-navigation:' not in css
        assert '--color-header-navigation-hover' not in css

    def test_organizer_regenerate_css_applies_header_colors_to_organizer_file(self):
        self.orga.settings.header_background_color = '#abcdef'
        self.orga.settings.navigation_text_color = '#fedcba'
        regenerate_organizer_css.apply(args=(self.orga.pk,))
        self.orga.settings.flush()
        assert self.orga.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.orga.settings.presale_css_file)) as c:
            content = c.read()
            assert '--color-header-background: #abcdef' in content
            assert '--color-header-navigation: #fedcba' in content

    def test_event_inherits_header_colors_from_organizer(self):
        self.orga.settings.header_background_color = '#112233'
        self.orga.settings.navigation_text_color = '#445566'
        regenerate_organizer_css.apply(args=(self.orga.pk,))
        self.event.settings.flush()
        assert self.event.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.event.settings.presale_css_file)) as c:
            content = c.read()
            assert '--color-header-background: #112233' in content
            assert '--color-header-navigation: #445566' in content

    def test_event_own_header_color_overrides_organizer(self):
        from eventyay.presale.style import regenerate_css
        self.orga.settings.header_background_color = '#000000'
        self.event.settings.header_background_color = '#ffffff'
        regenerate_css.apply(args=(self.event.pk,))
        self.event.settings.flush()
        assert self.event.settings.presale_css_file
        with open(os.path.join(settings.MEDIA_ROOT, self.event.settings.presale_css_file)) as c:
            content = c.read()
            assert '--color-header-background: #ffffff' in content
            assert '--color-header-background: #000000' not in content

    def test_existing_scss_variables_still_emitted(self):
        from eventyay.presale.style import compile_scss
        self.orga.settings.primary_color = '#33c33c'
        self.orga.settings.theme_color_success = '#00ff00'
        self.orga.settings.theme_color_danger = '#ff0000'
        css, _ = compile_scss(self.orga)
        assert '#33c33c' in css
        assert '#00ff00' in css
        assert '#ff0000' in css

    def test_event_css_view_with_font_target_orga(self):
        from django.urls import reverse
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
