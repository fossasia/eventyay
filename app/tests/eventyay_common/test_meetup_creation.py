from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import Organizer, Room
from eventyay.base.models import Quota
from eventyay.base.models.product import Product
from eventyay.base.models.auth import User
from eventyay.base.models import Team, Event
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.forms.event import MeetupEventWizardBasicsForm


def _make_user(email='organizer@example.com'):
    return User.objects.create_user(email=email, password='testpass123', locale='en')


def _make_organizer(slug='testorg'):
    return Organizer.objects.create(name='Test Org', slug=slug)


def _grant_team(user, organizer):
    team = Team.objects.create(
        organizer=organizer,
        name='Full Access',
        all_events=True,
        can_create_events=True,
        can_change_teams=True,
        can_change_organizer_settings=True,
        can_change_event_settings=True,
        can_change_items=True,
        can_view_orders=True,
        can_change_orders=True,
    )
    team.members.add(user)
    return team


def _basics_form(organizer, user, data):
    now = timezone.now()
    defaults = {
        'basics-name_0': 'Test Meetup',
        'basics-slug': 'test-meetup-slug',
        'basics-currency': 'EUR',
        'basics-locale': 'en',
        'basics-timezone': 'UTC',
        'basics-date_from_0': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
        'basics-date_from_1': '10:00:00',
        'basics-date_to_0': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
        'basics-date_to_1': '18:00:00',
    }
    defaults.update(data)

    class _FakeSession(dict):
        session_key = 'fakesessionkey'

    return MeetupEventWizardBasicsForm(
        data=defaults,
        prefix='basics',
        organizer=organizer,
        user=user,
        session=_FakeSession(),
        has_subevents=False,
        locales=['en'],
        is_video_creation=False,
        restrict_locale_choices=False,
    )


class TestMeetupFormValidation(TestCase):
    def setUp(self):
        self.user = _make_user('form_user@example.com')
        self.organizer = _make_organizer('formorg')
        _grant_team(self.user, self.organizer)

    def test_video_type_without_video_url_raises_error_on_video_url(self):
        form = _basics_form(self.organizer, self.user, {
            'basics-video_type': 'youtube',
            'basics-video_url': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('video_url', form.errors)
        self.assertIn(
            'A URL is required when a video type is selected.',
            form.errors['video_url'],
        )

    def test_video_url_without_video_type_raises_error_on_video_type(self):
        form = _basics_form(self.organizer, self.user, {
            'basics-video_type': '',
            'basics-video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('video_type', form.errors)
        self.assertIn(
            'A video type is required when a URL is provided.',
            form.errors['video_type'],
        )

    def test_both_video_type_and_video_url_is_valid(self):
        form = _basics_form(self.organizer, self.user, {
            'basics-video_type': 'youtube',
            'basics-video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        })
        self.assertNotIn('video_type', form.errors)
        self.assertNotIn('video_url', form.errors)

    def test_neither_video_type_nor_video_url_is_valid(self):
        form = _basics_form(self.organizer, self.user, {
            'basics-video_type': '',
            'basics-video_url': '',
        })
        self.assertNotIn('video_type', form.errors)
        self.assertNotIn('video_url', form.errors)


class TestEventCreateViewMeetupProvisioning(TestCase):
    def setUp(self):
        self.user = _make_user('creator@example.com')
        self.organizer = _make_organizer('meetuporg')
        _grant_team(self.user, self.organizer)
        self.client.force_login(self.user)
        gs = GlobalSettingsObject()
        gs.settings.set('meetup_creation_enabled', True)

    def tearDown(self):
        gs = GlobalSettingsObject()
        gs.settings.set('meetup_creation_enabled', False)

    def _post_create_meetup(self, extra_basics=None):
        now = timezone.now()
        data = {
            'foundation-organizer': str(self.organizer.pk),
            'foundation-locales': 'en',
            'foundation-has_subevents': '',
            'foundation-is_video_creation': '',
            'is_meetup': 'on',
            'basics-name_0': 'My Meetup',
            'basics-slug': 'my-meetup-slug',
            'basics-currency': 'EUR',
            'basics-locale': 'en',
            'basics-timezone': 'UTC',
            'basics-date_from_0': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
            'basics-date_from_1': '10:00:00',
            'basics-date_to_0': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
            'basics-date_to_1': '18:00:00',
            'basics-video_type': '',
            'basics-video_url': '',
        }
        if extra_basics:
            data.update(extra_basics)
        url = reverse('eventyay_common:events.add')
        return self.client.post(url, data, follow=True)

    def test_meetup_event_created_with_event_type_setting(self):
        self._post_create_meetup()
        with scopes_disabled():
            event = Event.objects.filter(organizer=self.organizer).first()
        self.assertIsNotNone(event, 'Event should have been created')
        event.settings.flush()
        self.assertEqual(event.settings.get('event_type'), 'meetup')

    def test_meetup_creates_main_room(self):
        self._post_create_meetup()
        with scopes_disabled():
            event = Event.objects.filter(organizer=self.organizer).first()
            self.assertIsNotNone(event)
            room = Room.objects.filter(event=event, deleted=False).first()
        self.assertIsNotNone(room, 'A Room should be auto-provisioned for a meetup event')

    def test_meetup_creates_rsvp_ticket_product(self):
        self._post_create_meetup()
        with scopes_disabled():
            event = Event.objects.filter(organizer=self.organizer).first()
            self.assertIsNotNone(event)
            product = Product.objects.filter(event=event, admission=True).first()
        self.assertIsNotNone(product, 'Product with admission=True should be auto-provisioned')
        self.assertEqual(product.default_price, Decimal('0.00'))
        self.assertTrue(product.admission)

    def test_meetup_creates_rsvp_quota(self):
        self._post_create_meetup()
        with scopes_disabled():
            event = Event.objects.filter(organizer=self.organizer).first()
            self.assertIsNotNone(event)
            quota = Quota.objects.filter(event=event, size__isnull=True).first()
        self.assertIsNotNone(quota, 'Quota with size=None (unlimited) should exist')
        self.assertIsNone(quota.size, 'Quota size should be None (unlimited)')
        with scopes_disabled():
            product = Product.objects.filter(event=event, admission=True).first()
            self.assertIn(product, quota.products.all())

    def test_meetup_room_module_config_for_youtube(self):
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        self._post_create_meetup({
            'basics-video_type': 'youtube',
            'basics-video_url': url,
        })
        with scopes_disabled():
            event = Event.objects.filter(organizer=self.organizer).first()
            self.assertIsNotNone(event)
            room = Room.objects.filter(event=event, deleted=False).first()
        self.assertIsNotNone(room)
        expected = [{'type': 'livestream.youtube', 'config': {'ytid': url}}]
        self.assertEqual(room.module_config, expected)

    def test_meetup_room_module_config_is_empty_without_video_type(self):
        self._post_create_meetup({
            'basics-video_type': '',
            'basics-video_url': '',
        })
        with scopes_disabled():
            event = Event.objects.filter(organizer=self.organizer).first()
            self.assertIsNotNone(event)
            room = Room.objects.filter(event=event, deleted=False).first()
        self.assertIsNotNone(room)
        self.assertEqual(room.module_config, [])


class TestStandardEventCreationNoProvisioning(TestCase):
    def setUp(self):
        self.user = _make_user('standard@example.com')
        self.organizer = _make_organizer('standardorg')
        _grant_team(self.user, self.organizer)
        self.client.force_login(self.user)
        gs = GlobalSettingsObject()
        gs.settings.set('meetup_creation_enabled', True)

    def tearDown(self):
        gs = GlobalSettingsObject()
        gs.settings.set('meetup_creation_enabled', False)

    def test_standard_event_does_not_create_room_product_quota(self):
        now = timezone.now()
        data = {
            'foundation-organizer': str(self.organizer.pk),
            'foundation-locales': 'en',
            'foundation-has_subevents': '',
            'foundation-is_video_creation': '',
            'basics-name_0': 'Standard Event',
            'basics-slug': 'standard-event-slug',
            'basics-currency': 'EUR',
            'basics-locale': 'en',
            'basics-timezone': 'UTC',
            'basics-date_from_0': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
            'basics-date_from_1': '10:00:00',
            'basics-date_to_0': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
            'basics-date_to_1': '18:00:00',
        }
        url = reverse('eventyay_common:events.add')
        self.client.post(url, data, follow=True)

        with scopes_disabled():
            event = Event.objects.filter(organizer=self.organizer).first()
        self.assertIsNotNone(event, 'Event should still be created')
        event.settings.flush()
        self.assertNotEqual(event.settings.get('event_type'), 'meetup')

        with scopes_disabled():
            rooms = Room.objects.filter(event=event)
            products = Product.objects.filter(event=event)
            quotas = Quota.objects.filter(event=event)

        self.assertEqual(rooms.count(), 0, 'No rooms should be auto-provisioned for standard events')
        self.assertEqual(products.count(), 0, 'No products should be auto-provisioned for standard events')
        self.assertEqual(quotas.count(), 0, 'No quotas should be auto-provisioned for standard events')


class TestMeetupCreationGate(TestCase):
    def setUp(self):
        self.user = _make_user('gatetest@example.com')
        self.organizer = _make_organizer('gateorg')
        _grant_team(self.user, self.organizer)
        self.client.force_login(self.user)
        gs = GlobalSettingsObject()
        gs.settings.set('meetup_creation_enabled', False)

    def test_meetup_creation_disabled_returns_403(self):
        url = reverse('eventyay_common:events.add') + '?meetup=1'
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            403,
            'Should raise PermissionDenied (HTTP 403) when meetup creation is disabled',
        )

    def test_meetup_creation_post_disabled_returns_403(self):
        now = timezone.now()
        data = {
            'foundation-organizer': str(self.organizer.pk),
            'foundation-locales': 'en',
            'foundation-has_subevents': '',
            'foundation-is_video_creation': '',
            'is_meetup': 'on',
            'basics-name_0': 'Blocked Meetup',
            'basics-slug': 'blocked-meetup',
            'basics-currency': 'EUR',
            'basics-locale': 'en',
            'basics-timezone': 'UTC',
            'basics-date_from_0': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
            'basics-date_from_1': '10:00:00',
            'basics-date_to_0': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
            'basics-date_to_1': '18:00:00',
        }
        url = reverse('eventyay_common:events.add')
        response = self.client.post(url, data)
        self.assertEqual(
            response.status_code,
            403,
            'Should raise PermissionDenied (HTTP 403) when meetup creation is disabled',
        )
