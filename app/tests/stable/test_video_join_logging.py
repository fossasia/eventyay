import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, OrderPosition, Organizer
from eventyay.base.models import Product as Item


User = get_user_model()


class VideoJoinLoggingTest(TestCase):
    """The video login token in the redirect URL must not be written to the log."""

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
            tickets_published=True,
            private_testmode=False,
        )
        self.event.settings.set('venueless_url', 'https://video.example.com/')
        self.event.settings.set('venueless_issuer', 'issuer')
        self.event.settings.set('venueless_audience', 'audience')
        self.event.settings.set('venueless_secret', 'a-test-secret-that-is-at-least-32-bytes')
        self.event.settings.set('venueless_all_products', True)
        ticket = Item.objects.create(event=self.event, name='Ticket', default_price=23, admission=True)
        User.objects.create_user(email='buyer@example.com', password='testpass123')
        order = Order.objects.create(
            status=Order.STATUS_PAID,
            event=self.event,
            email='buyer@example.com',
            datetime=now(),
            expires=now() + datetime.timedelta(days=11),
            total=Decimal('23'),
            locale='en',
        )
        position = OrderPosition.objects.create(order=order, product=ticket, price=Decimal('23'))
        self.join_url = (
            f'/{self.orga.slug}/{self.event.slug}/ticket/{order.code}/{position.positionid}/'
            f'{position.web_secret}/False/venueless/'
        )
        self.client.login(email='buyer@example.com', password='testpass123')

    def join(self):
        with self.assertLogs('eventyay.presale.views.order', level='INFO') as logs:
            response = self.client.post(self.join_url)
        self.assertEqual(response.status_code, 302)
        return response['Location'], '\n'.join(logs.output)

    def test_token_in_fragment_is_not_logged(self):
        location, output = self.join()
        token = location.split('#token=', 1)[1]
        self.assertTrue(token)
        self.assertNotIn(token, output)
        self.assertIn(self.event.slug, output)

    def test_token_in_url_template_is_not_logged(self):
        self.event.settings.set('venueless_url', 'https://video.example.com/login?token={token}')
        location, output = self.join()
        token = location.split('token=', 1)[1]
        self.assertTrue(token)
        self.assertNotIn(token, output)

    def test_presale_join_does_not_log_token(self):
        with self.assertLogs('eventyay.presale.views.event', level='INFO') as logs:
            response = self.client.get(f'/{self.orga.slug}/{self.event.slug}/online-video/join')
        self.assertEqual(response.status_code, 302, response.content)
        token = response['Location'].split('#token=', 1)[1]
        self.assertTrue(token)
        self.assertNotIn(token, '\n'.join(logs.output))

    def test_schedule_join_does_not_log_token(self):
        with scopes_disabled():
            self.event.talks_published = True
            self.event.save(update_fields=['talks_published'])
            self.event.release_schedule('v1')
        with self.assertLogs('eventyay.agenda.views.talk', level='INFO') as logs:
            response = self.client.get(
                reverse(
                    'agenda:event.onlinevideo.join',
                    kwargs={'organizer': self.orga.slug, 'event': self.event.slug},
                )
            )
        self.assertEqual(response.status_code, 302, response.content)
        token = response['Location'].split('#token=', 1)[1]
        self.assertTrue(token)
        self.assertNotIn(token, '\n'.join(logs.output))
