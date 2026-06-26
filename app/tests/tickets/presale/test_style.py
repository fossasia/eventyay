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
