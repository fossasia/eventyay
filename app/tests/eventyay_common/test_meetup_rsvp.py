import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import now
from django_scopes import scopes_disabled, scope

from eventyay.base.models import Event, Organizer, Order, Quota, User, Team
from eventyay.base.models.product import Product


def _make_user(email):
    return User.objects.create_user(email=email, password='testpass123', locale='en')


def _make_organizer(slug):
    return Organizer.objects.create(name=slug.title(), slug=slug)


def _grant_team(user, organizer):
    team = Team.objects.create(
        organizer=organizer,
        name='Full Access',
        all_events=True,
        can_create_events=True,
        can_change_event_settings=True,
        can_view_orders=True,
        can_change_orders=True,
    )
    team.members.add(user)
    return team


def _make_meetup_event(organizer, slug='my-meetup', live=True, presale_end=None):
    future = now() + datetime.timedelta(days=30)
    event = Event.objects.create(
        organizer=organizer,
        name='My Meetup',
        slug=slug,
        date_from=future,
        date_to=future + datetime.timedelta(hours=3),
        currency='USD',
        locale='en',
        live=live,
        email='meetup@example.com',
        presale_end=presale_end,
    )
    event.settings.set('event_type', 'meetup')
    return event


def _make_rsvp_product_quota(event):
    with scope(event=event):
        product = Product.objects.create(
            event=event,
            name='RSVP Ticket',
            default_price=Decimal('0.00'),
            admission=True,
            active=True,
        )
        quota = Quota.objects.create(
            event=event,
            name='RSVP',
            size=None,
        )
        quota.products.add(product)
    return product, quota


def _make_standard_event(organizer, slug='standard-event'):
    future = now() + datetime.timedelta(days=30)
    return Event.objects.create(
        organizer=organizer,
        name='Standard Event',
        slug=slug,
        date_from=future,
        date_to=future + datetime.timedelta(hours=3),
        currency='USD',
        locale='en',
        live=True,
        email='standard@example.com',
    )


class TestAuthenticatedRsvp(TestCase):
    @scopes_disabled()
    def setUp(self):
        self.user = _make_user('rsvp_user@example.com')
        self.organizer = _make_organizer('rsvporg')
        _grant_team(self.user, self.organizer)
        self.event = _make_meetup_event(self.organizer)
        _make_rsvp_product_quota(self.event)
        self.client.force_login(self.user)
        self.rsvp_url = f'/{self.organizer.slug}/{self.event.slug}/rsvp/'

    def test_authenticated_rsvp_creates_paid_order(self):
        response = self.client.post(self.rsvp_url, follow=True)

        with scopes_disabled():
            orders = Order.objects.filter(
                event=self.event,
                email=self.user.email,
            )
        self.assertEqual(orders.count(), 1)
        order = orders.first()
        self.assertEqual(order.status, Order.STATUS_PAID)
        self.assertEqual(response.status_code, 200)

    def test_second_authenticated_rsvp_does_not_duplicate_order(self):
        self.client.post(self.rsvp_url)

        with scopes_disabled():
            count_after_first = Order.objects.filter(
                event=self.event,
                email=self.user.email,
            ).count()
        self.assertEqual(count_after_first, 1)

        response = self.client.post(self.rsvp_url)

        with scopes_disabled():
            count_after_second = Order.objects.filter(
                event=self.event,
                email=self.user.email,
            ).count()

        self.assertEqual(count_after_second, 1)
        self.assertIn(response.status_code, [301, 302])


class TestGuestRsvp(TestCase):
    @scopes_disabled()
    def setUp(self):
        self.organizer = _make_organizer('guestrsvporg')
        self.event = _make_meetup_event(self.organizer, slug='guest-meetup')
        _make_rsvp_product_quota(self.event)
        self.event.settings.set('require_registered_account_for_tickets', False)
        self.rsvp_url = f'/{self.organizer.slug}/{self.event.slug}/rsvp/'

    def test_guest_rsvp_with_valid_data_creates_paid_order(self):
        response = self.client.post(self.rsvp_url, {
            'attendee_name': 'Jane Guest',
            'attendee_email': 'jane@example.com',
        }, follow=True)

        with scopes_disabled():
            orders = Order.objects.filter(
                event=self.event,
                email='jane@example.com',
            )
        self.assertEqual(orders.count(), 1)
        order = orders.first()
        self.assertEqual(order.status, Order.STATUS_PAID)
        self.assertEqual(response.status_code, 200)

    def test_guest_rsvp_missing_name_returns_form_errors(self):
        response = self.client.post(self.rsvp_url, {
            'attendee_name': '',
            'attendee_email': 'jane@example.com',
        })

        self.assertEqual(response.status_code, 200)
        with scopes_disabled():
            self.assertEqual(Order.objects.filter(event=self.event).count(), 0)

    def test_guest_rsvp_invalid_email_returns_form_errors(self):
        response = self.client.post(self.rsvp_url, {
            'attendee_name': 'Jane Guest',
            'attendee_email': 'not-a-valid-email',
        })

        self.assertEqual(response.status_code, 200)
        with scopes_disabled():
            self.assertEqual(Order.objects.filter(event=self.event).count(), 0)


class TestRsvpViewOnNonMeetupEvent(TestCase):
    @scopes_disabled()
    def setUp(self):
        self.organizer = _make_organizer('stdorg')
        self.event = _make_standard_event(self.organizer, slug='std-event')
        self.rsvp_url = f'/{self.organizer.slug}/{self.event.slug}/rsvp/'

    def test_rsvp_on_non_meetup_event_returns_404(self):
        response = self.client.post(self.rsvp_url, {
            'attendee_name': 'Someone',
            'attendee_email': 'someone@example.com',
        })
        self.assertEqual(response.status_code, 404)


class TestRsvpViewPresaleNotRunning(TestCase):
    @scopes_disabled()
    def setUp(self):
        self.organizer = _make_organizer('expiredorg')
        past = now() - datetime.timedelta(days=1)
        self.event = _make_meetup_event(
            self.organizer,
            slug='expired-meetup',
            presale_end=past,
        )
        _make_rsvp_product_quota(self.event)
        self.rsvp_url = f'/{self.organizer.slug}/{self.event.slug}/rsvp/'
        self.index_url = f'/{self.organizer.slug}/{self.event.slug}/'

    def test_rsvp_when_presale_not_running_redirects_with_error(self):
        response = self.client.post(self.rsvp_url, follow=False)

        self.assertIn(response.status_code, [301, 302])
        redirect_location = response.get('Location', '')
        self.assertIn(self.event.slug, redirect_location)

        with scopes_disabled():
            self.assertEqual(Order.objects.filter(event=self.event).count(), 0)


class TestEventIndexMeetupContext(TestCase):
    @scopes_disabled()
    def setUp(self):
        self.organizer = _make_organizer('ctxorg')
        self.meetup_event = _make_meetup_event(self.organizer, slug='ctx-meetup')
        _make_rsvp_product_quota(self.meetup_event)
        self.standard_event = _make_standard_event(self.organizer, slug='ctx-standard')

    def test_meetup_event_sets_is_meetup_event_true(self):
        url = f'/{self.organizer.slug}/{self.meetup_event.slug}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context['is_meetup_event'], True)

    def test_standard_event_sets_is_meetup_event_false(self):
        url = f'/{self.organizer.slug}/{self.standard_event.slug}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context['is_meetup_event'], False)
