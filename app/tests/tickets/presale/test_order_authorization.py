"""
Tests for order authorization and access control.
Tests ensure that unauthenticated users and users who don't own orders
cannot access protected order actions.
"""
import datetime
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Event,
    Product as Item,
    ProductCategory as ItemCategory,
    Order,
    OrderPosition,
    Organizer,
    Quota,
)
from eventyay.base.models.orders import OrderPayment


User = get_user_model()


class OrderAuthorizationTest(TestCase):
    """Test authorization for order operations."""

    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.client = Client()
        
        self.orga = Organizer.objects.create(name='CCC', slug='ccc')
        self.event = Event.objects.create(
            organizer=self.orga,
            name='30C3',
            slug='30c3',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
            plugins='eventyay.plugins.stripe,eventyay.plugins.banktransfer',
            live=True,
            tickets_published=True,
            private_testmode=False,
        )
        self.event.settings.set('payment_banktransfer__enabled', True)

        self.category = ItemCategory.objects.create(event=self.event, name='Everything', position=0)
        self.quota = Quota.objects.create(event=self.event, name='Tickets', size=5)
        self.ticket = Item.objects.create(
            event=self.event,
            name='Ticket',
            category=self.category,
            default_price=23,
            admission=True,
        )
        self.quota.products.add(self.ticket)

        # Create two users
        self.user_a = User.objects.create_user(
            email='user_a@example.com',
            password='testpass123'
        )
        self.user_b = User.objects.create_user(
            email='user_b@example.com',
            password='testpass123'
        )

        # Create order for User A
        self.order_a = Order.objects.create(
            status=Order.STATUS_PENDING,
            event=self.event,
            email='user_a@example.com',
            datetime=now() - datetime.timedelta(days=3),
            expires=now() + datetime.timedelta(days=11),
            total=Decimal('23'),
            locale='en',
        )
        OrderPosition.objects.create(
            order=self.order_a,
            product=self.ticket,
            price=Decimal('23'),
            attendee_name_parts={'full_name': 'User A'},
        )

        # Create order for User B
        self.order_b = Order.objects.create(
            status=Order.STATUS_PENDING,
            event=self.event,
            email='user_b@example.com',
            datetime=now() - datetime.timedelta(days=3),
            expires=now() + datetime.timedelta(days=11),
            total=Decimal('23'),
            locale='en',
        )
        OrderPosition.objects.create(
            order=self.order_b,
            product=self.ticket,
            price=Decimal('23'),
            attendee_name_parts={'full_name': 'User B'},
        )

    def test_unauthenticated_user_cannot_modify_order(self):
        """Unauthenticated user should be redirected to login when trying to modify order."""
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/modify',
            follow=False
        )
        # Should redirect to login page
        self.assertIn(response.status_code, [301, 302])

    def test_unauthenticated_user_cannot_cancel_order(self):
        """Unauthenticated user should be redirected to login when trying to cancel order."""
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/cancel',
            follow=False
        )
        # Should redirect to login page
        self.assertIn(response.status_code, [301, 302])

    def test_unauthenticated_user_cannot_change_order(self):
        """Unauthenticated user should be redirected to login when trying to change order."""
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/change',
            follow=False
        )
        # Should redirect to login page
        self.assertIn(response.status_code, [301, 302])

    def test_different_user_cannot_modify_order(self):
        """User B cannot modify User A's order."""
        self.client.login(email='user_b@example.com', password='testpass123')
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/modify',
            follow=True
        )
        # Nothing to modify redirects to the order page, which returns 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_different_user_cannot_cancel_order(self):
        """User B cannot cancel User A's order."""
        self.client.login(email='user_b@example.com', password='testpass123')
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/cancel',
            follow=False
        )
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_different_user_cannot_change_order(self):
        """User B cannot change User A's order."""
        self.client.login(email='user_b@example.com', password='testpass123')
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/change',
            follow=True
        )
        # Nothing to change redirects to the order page, which returns 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_generate_invoice(self):
        """Unauthenticated user cannot generate invoice."""
        response = self.client.post(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/invoice',
            follow=False
        )
        # Should redirect to login page
        self.assertIn(response.status_code, [301, 302])

    def test_different_user_cannot_generate_invoice(self):
        """User B cannot generate invoice for User A's order."""
        self.client.login(email='user_b@example.com', password='testpass123')
        response = self.client.post(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/invoice',
            follow=False
        )
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_owner_can_view_order_details(self):
        """Order owner should be able to view order details."""
        self.client.login(email='user_a@example.com', password='testpass123')
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/'
        )
        # Should be allowed to view
        self.assertIn(response.status_code, [200])

    def test_unauthenticated_cannot_view_order_details(self):
        """Unauthenticated users should be redirected to login when viewing order details."""
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/',
            follow=False
        )
        # Should redirect to login page
        self.assertIn(response.status_code, [301, 302])

    def test_different_user_cannot_view_order_details(self):
        """User B cannot view User A's order details."""
        self.client.login(email='user_b@example.com', password='testpass123')
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/',
            follow=False
        )
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_guest_can_view_order_details_when_guest_orders_allowed(self):
        """Without an account, the secret order URL is the only way in when guest orders are allowed."""
        self.event.settings.set('require_registered_account_for_tickets', False)
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/'
        )
        self.assertEqual(response.status_code, 200)

    def test_guest_can_view_confirmation_after_checkout_when_guest_orders_allowed(self):
        """The page checkout redirects to after placing an order is reachable without an account."""
        self.event.settings.set('require_registered_account_for_tickets', False)
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/?thanks=1'
        )
        self.assertEqual(response.status_code, 200)

    def test_guest_with_wrong_secret_cannot_view_order_when_guest_orders_allowed(self):
        """Allowing guest orders does not open orders to visitors without the secret."""
        self.event.settings.set('require_registered_account_for_tickets', False)
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/wrongsecret/',
            follow=False,
        )
        self.assertNotEqual(response.status_code, 200)

    def test_different_user_cannot_view_order_details_when_guest_orders_allowed(self):
        """A logged-in user who does not own the order is still denied when guest orders are allowed."""
        self.event.settings.set('require_registered_account_for_tickets', False)
        self.client.login(email='user_b@example.com', password='testpass123')
        response = self.client.get(
            f'/{self.event.organizer.slug}/{self.event.slug}/order/{self.order_a.code}/{self.order_a.secret}/',
            follow=False,
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_cannot_join_video_when_guest_orders_allowed(self):
        """Joining the online event still requires the authenticated order owner."""
        self.event.settings.set('require_registered_account_for_tickets', False)
        with scopes_disabled():
            position = self.order_a.positions.first()
        response = self.client.post(
            f'/{self.event.organizer.slug}/{self.event.slug}/ticket/{self.order_a.code}/{position.positionid}/{position.web_secret}/False/venueless/',
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])
