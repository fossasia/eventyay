import datetime
import json
import re
from decimal import Decimal

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled
from freezegun import freeze_time

from eventyay.base.models import Order, OrderPosition
from eventyay.presale.style import regenerate_css, regenerate_organizer_css

from .test_cart import CartTestMixin


# Mirrors eventRootFromCartAddUrl() in pretixpresale/js/widget/widget.js
_WIDGET_CART_ADD_RE = re.compile(r'/(?:w|widget)/[a-zA-Z0-9]{16}/cart/add(?=[/?#]|$)')


def event_root_from_cart_add_url(response_url):
    matches = list(_WIDGET_CART_ADD_RE.finditer(response_url))
    if not matches:
        return None
    root = response_url[: matches[-1].start()]
    if not root.endswith('/'):
        root += '/'
    return root


def shop_is_secure(target_url, page_protocol='http:'):
    # Mirrors shop_is_secure() in pretixpresale/js/widget/widget.js
    if target_url and re.match(r'^https:', target_url, re.I):
        return True
    return bool(re.match(r'^https:', page_protocol, re.I))


class WidgetCartTest(CartTestMixin, TestCase):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            status=Order.STATUS_PENDING,
            event=self.event,
            email='admin@localhost',
            datetime=now() - datetime.timedelta(days=3),
            expires=now() + datetime.timedelta(days=11),
            total=Decimal('23'),
            locale='en',
        )
        self.ticket_pos = OrderPosition.objects.create(
            order=self.order,
            product=self.ticket,
            variation=None,
            price=Decimal('23'),
            attendee_name_parts={'full_name': 'Peter'},
        )

    def test_iframe_entry_view_wrapper(self):
        self.client.get('/%s/%s/?iframe=1&locale=de' % (self.orga.slug, self.event.slug))
        assert 'iframe_session' in self.client.session
        assert self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value == 'de'

    def test_allow_frame_if_namespaced(self):
        response = self.client.get('/%s/%s/' % (self.orga.slug, self.event.slug))
        assert 'X-Frame-Options' in response
        response = self.client.get('/%s/%s/w/aaaaaaaaaaaaaaaa/' % (self.orga.slug, self.event.slug))
        assert 'X-Frame-Options' not in response
        response = self.client.get('/%s/%s/widget/aaaaaaaaaaaaaaaa/' % (self.orga.slug, self.event.slug))
        assert 'X-Frame-Options' not in response

        response = self.client.get('/%s/%s/waitinglist' % (self.orga.slug, self.event.slug))
        assert 'X-Frame-Options' in response
        response = self.client.get('/%s/%s/w/aaaaaaaaaaaaaaaa/waitinglist' % (self.orga.slug, self.event.slug))
        assert 'X-Frame-Options' not in response
        response = self.client.get('/%s/%s/widget/aaaaaaaaaaaaaaaa/waitinglist' % (self.orga.slug, self.event.slug))
        assert 'X-Frame-Options' not in response
        response = self.client.get('/%s/%s/widget/aaaaaaaaaaaaaaaa/waitinglist/' % (self.orga.slug, self.event.slug))
        assert 'X-Frame-Options' not in response

    def test_allow_frame_on_order(self):
        response = self.client.get(
            '/%s/%s/order/%s/%s/' % (self.orga.slug, self.event.slug, self.order.code, self.order.secret)
        )
        assert 'X-Frame-Options' not in response
        response = self.client.get(
            '/%s/%s/order/%s/%s/modify' % (self.orga.slug, self.event.slug, self.order.code, self.order.secret)
        )
        assert 'X-Frame-Options' not in response
        response = self.client.get(
            '/%s/%s/order/%s/%s/pay/change' % (self.orga.slug, self.event.slug, self.order.code, self.order.secret)
        )
        assert 'X-Frame-Options' not in response
        response = self.client.get(
            '/%s/%s/order/%s/%s/cancel' % (self.orga.slug, self.event.slug, self.order.code, self.order.secret)
        )
        assert 'X-Frame-Options' not in response

    def test_allow_cors_if_namespaced(self):
        response = self.client.post(
            '/%s/%s/cart/add' % (self.orga.slug, self.event.slug),
            {'item_%d' % self.ticket.id: '1', 'ajax': 1},
        )
        assert 'Access-Control-Allow-Origin' not in response
        response = self.client.post(
            '/%s/%s/w/aaaaaaaaaaaaaaaa/cart/add' % (self.orga.slug, self.event.slug),
            {'item_%d' % self.ticket.id: '1', 'ajax': 1},
        )
        assert response['Access-Control-Allow-Origin'] == '*'
        response = self.client.post(
            '/%s/%s/widget/aaaaaaaaaaaaaaaa/cart/add' % (self.orga.slug, self.event.slug),
            {'item_%d' % self.ticket.id: '1', 'ajax': 1},
        )
        assert response['Access-Control-Allow-Origin'] == '*'

    def test_widget_namespace_routes(self):
        # Widget checkout flow redirects straight to checkout after add-to-cart.
        self.event.settings.set('redirect_to_checkout_directly', True)

        ns = 'bbbbbbbbbbbbbbbb'
        assert reverse(
            'presale:event.cart.add',
            kwargs={'organizer': self.orga.slug, 'event': self.event.slug, 'cart_namespace': ns},
        ) == '/%s/%s/widget/%s/cart/add' % (self.orga.slug, self.event.slug, ns)
        assert reverse(
            'presale:event.index',
            kwargs={'organizer': self.orga.slug, 'event': self.event.slug, 'cart_namespace': ns},
        ) == '/%s/%s/widget/%s/' % (self.orga.slug, self.event.slug, ns)

        response = self.client.post(
            '/%s/%s/widget/%s/cart/add' % (self.orga.slug, self.event.slug, ns),
            {'item_%d' % self.ticket.id: '1', 'ajax': 1},
        )
        assert response.status_code == 200
        assert response['Access-Control-Allow-Origin'] == '*'
        data = response.json()
        assert data.get('success') is True
        assert '/widget/%s/checkout/start' % ns in data.get('redirect', '')

        response = self.client.get(
            '/%s/%s/widget/%s/checkout/start' % (self.orga.slug, self.event.slug, ns),
            {'take_cart_id': data.get('cart_id', '').split('@')[0], 'iframe': '1'},
        )
        self.assertRedirects(
            response,
            '/%s/%s/widget/%s/checkout/questions/' % (self.orga.slug, self.event.slug, ns),
            fetch_redirect_response=False,
        )

        response = self.client.get(
            '/%s/%s/widget/%s/redeem/' % (self.orga.slug, self.event.slug, ns),
            {'iframe': '1'},
        )
        assert response.status_code != 404
        assert 'X-Frame-Options' not in response

    def test_iframe_checkout_login_interstitial(self):
        # Login itself is X-Frame-Options: DENY; widget iframes must not redirect there.
        self.event.settings.set('require_registered_account_for_tickets', True)
        self.event.settings.set('redirect_to_checkout_directly', True)

        ns = 'cccccccccccccccc'
        response = self.client.post(
            '/%s/%s/widget/%s/cart/add' % (self.orga.slug, self.event.slug, ns),
            {'item_%d' % self.ticket.id: '1', 'ajax': 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True

        response = self.client.get(
            '/%s/%s/widget/%s/checkout/start' % (self.orga.slug, self.event.slug, ns),
            {'take_cart_id': data.get('cart_id', '').split('@')[0], 'iframe': '1'},
        )
        assert response.status_code == 200
        assert 'X-Frame-Options' not in response
        assert b'/login/' in response.content
        assert b'target="_blank"' in response.content
        assert b'Please log in' in response.content

    def test_regular_checkout_ignores_stale_iframe_session(self):
        # A prior ?iframe=1 visit must not force the framable login interstitial on
        # ordinary (non-namespaced) checkout — that would bypass normal frame protection.
        self.event.settings.set('require_registered_account_for_tickets', True)
        self.event.settings.set('redirect_to_checkout_directly', True)

        response = self.client.get(
            '/%s/%s/' % (self.orga.slug, self.event.slug),
            {'iframe': '1'},
        )
        assert response.status_code == 200
        assert self.client.session.get('iframe_session') is True

        response = self.client.post(
            '/%s/%s/cart/add' % (self.orga.slug, self.event.slug),
            {'item_%d' % self.ticket.id: '1', 'ajax': 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True

        response = self.client.get(
            '/%s/%s/checkout/start' % (self.orga.slug, self.event.slug),
            {'take_cart_id': data.get('cart_id', '').split('@')[0]},
        )
        assert response.status_code == 302
        assert '/login/' in response['Location']
        assert b'target="_blank"' not in response.content

    def test_widget_js_waitinglist_uses_product_param(self):
        path = finders.find('pretixpresale/js/widget/widget.js')
        assert path
        with open(path, encoding='utf-8') as fp:
            js = fp.read()
        assert "waitinglist?product=" in js
        assert "waitinglist?item=" not in js

    def test_event_root_from_cart_add_url_uses_final_namespaced_suffix(self):
        # Keep the Python mirror in sync with widget.js (avoids first-/cart/add slug traps).
        path = finders.find('pretixpresale/js/widget/widget.js')
        with open(path, encoding='utf-8') as fp:
            js = fp.read()
        # Source stores the regex with JS escapes (\/); normalize for the sync check.
        assert r'/(?:w|widget)/[a-zA-Z0-9]{16}/cart/add(?=[/?#]|$)' in js.replace('\\/', '/')
        assert 'shop_is_secure(this.target_url)' in js

        ns = 'abcdefghijklmnop'
        assert (
            event_root_from_cart_add_url(
                'https://shop.example/orga/ev/widget/%s/cart/add' % ns
            )
            == 'https://shop.example/orga/ev/'
        )
        assert (
            event_root_from_cart_add_url(
                'https://shop.example/orga/ev/w/%s/cart/add?iframe=1' % ns
            )
            == 'https://shop.example/orga/ev/'
        )
        # Slug path contains "/cart/add" before the real namespaced cart-add.
        assert (
            event_root_from_cart_add_url(
                'https://shop.example/cart/add/ev/widget/%s/cart/add' % ns
            )
            == 'https://shop.example/cart/add/ev/'
        )
        assert event_root_from_cart_add_url('https://shop.example/orga/ev/cart/add') is None

        current = 'https://shop.example/orga/ev/'
        same_root = event_root_from_cart_add_url(
            'https://shop.example/orga/ev/widget/%s/cart/add' % ns
        )
        other_root = event_root_from_cart_add_url(
            'https://other.example/orga/ev/widget/%s/cart/add' % ns
        )
        # Mirrors buy_error_callback: retry only when recovered root differs.
        assert same_root == current
        assert not (same_root and same_root != current)
        assert other_root and other_root != current
        assert not (None and None != current)

    def test_shop_is_secure_prefers_target_url_protocol(self):
        # HTTP embed page + HTTPS shop must still allow iframe checkout.
        assert shop_is_secure('https://shop.example/orga/ev/', 'http:') is True
        assert shop_is_secure('http://shop.example/orga/ev/', 'http:') is False
        assert shop_is_secure('http://shop.example/orga/ev/', 'https:') is True
        assert shop_is_secure('', 'https:') is True
        assert shop_is_secure(None, 'http:') is False

    def test_widget_waitinglist_accepts_product_query_param(self):
        self.event.settings.set('waiting_list_enabled', True)
        self.ticket.allow_waitinglist = True
        self.ticket.save()
        response = self.client.get(
            '/%s/%s/widget/aaaaaaaaaaaaaaaa/waitinglist' % (self.orga.slug, self.event.slug),
            {'product': self.ticket.id},
        )
        assert response.status_code == 200
        assert 'waiting list' in response.rendered_content.lower()

        # Legacy item= is not accepted by WaitingView.product_and_variation.
        response = self.client.get(
            '/%s/%s/widget/aaaaaaaaaaaaaaaa/waitinglist' % (self.orga.slug, self.event.slug),
            {'item': self.ticket.id},
            follow=False,
        )
        assert response.status_code == 302

    def test_cart_isolation(self):
        response = self.client.post(
            '/%s/%s/cart/add' % (self.orga.slug, self.event.slug),
            {'item_%d' % self.ticket.id: '1'},
            follow=True,
        )
        self.assertRedirects(
            response,
            '/%s/%s/?require_cookie=true' % (self.orga.slug, self.event.slug),
            target_status_code=200,
        )
        doc = BeautifulSoup(response.rendered_content, 'lxml')
        assert len(doc.select('.cart .cart-row')) == 2
        self.assertIn('Early-bird', doc.select('.cart .cart-row')[0].select('strong')[0].text)
        self.assertIn('1', doc.select('.cart .cart-row')[0].select('.count')[0].text)
        self.assertIn('23', doc.select('.cart .cart-row')[0].select('.price')[0].text)
        self.assertIn('23', doc.select('.cart .cart-row')[0].select('.price')[1].text)

        response = self.client.get('/%s/%s/w/aaaaaaaaaaaaaaaa/' % (self.orga.slug, self.event.slug))
        doc = BeautifulSoup(response.rendered_content, 'lxml')
        assert len(doc.select('.cart .cart-row')) == 0
        response = self.client.post(
            '/%s/%s/w/aaaaaaaaaaaaaaaa/cart/add' % (self.orga.slug, self.event.slug),
            {'item_%d' % self.ticket.id: '1'},
            follow=True,
        )
        self.assertRedirects(
            response,
            '/%s/%s/widget/aaaaaaaaaaaaaaaa/?require_cookie=true' % (self.orga.slug, self.event.slug),
            target_status_code=200,
        )
        doc = BeautifulSoup(response.rendered_content, 'lxml')
        assert len(doc.select('.cart .cart-row')) == 2
        self.assertIn('Early-bird', doc.select('.cart .cart-row')[0].select('strong')[0].text)
        self.assertIn('1', doc.select('.cart .cart-row')[0].select('.count')[0].text)
        self.assertIn('23', doc.select('.cart .cart-row')[0].select('.price')[0].text)
        self.assertIn('23', doc.select('.cart .cart-row')[0].select('.price')[1].text)

        response = self.client.get('/%s/%s/w/aaaaaaaaaaaaaaab/' % (self.orga.slug, self.event.slug))
        doc = BeautifulSoup(response.rendered_content, 'lxml')
        assert len(doc.select('.cart .cart-row')) == 0
        response = self.client.post(
            '/%s/%s/w/aaaaaaaaaaaaaaab/cart/add' % (self.orga.slug, self.event.slug),
            {'item_%d' % self.ticket.id: '1'},
            follow=True,
        )
        self.assertRedirects(
            response,
            '/%s/%s/widget/aaaaaaaaaaaaaaab/?require_cookie=true' % (self.orga.slug, self.event.slug),
            target_status_code=200,
        )
        doc = BeautifulSoup(response.rendered_content, 'lxml')
        assert len(doc.select('.cart .cart-row')) == 2
        self.assertIn('Early-bird', doc.select('.cart .cart-row')[0].select('strong')[0].text)
        self.assertIn('1', doc.select('.cart .cart-row')[0].select('.count')[0].text)
        self.assertIn('23', doc.select('.cart .cart-row')[0].select('.price')[0].text)
        self.assertIn('23', doc.select('.cart .cart-row')[0].select('.price')[1].text)

    def test_saleschannel_disabled(self):
        self.event.sales_channels = []
        self.event.save()
        response = self.client.get('/%s/%s/widget/product_list' % (self.orga.slug, self.event.slug))
        data = json.loads(response.content.decode())
        assert data == {
            'error': 'Tickets for this event cannot be purchased on this sales channel.',
            'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
        }
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            '/%s/%s/w/aaaaaaaaaaaaaaab/cart/add' % (self.orga.slug, self.event.slug),
            {'item_%d' % self.ticket.id: '1'},
            follow=True,
        )
        self.assertEqual(response.status_code, 404)

    def test_product_list_view(self):
        response = self.client.get('/%s/%s/widget/product_list' % (self.orga.slug, self.event.slug))
        assert response['Access-Control-Allow-Origin'] == '*'
        data = json.loads(response.content.decode())
        assert data == {
            'name': '30C3',
            'date_range': f'Dec. 26th – 27th, {self.event.date_from.year} 00:00',
            'frontpage_text': '',
            'currency': 'EUR',
            'show_variations_expanded': False,
            'display_net_prices': False,
            'vouchers_exist': False,
            'waiting_list_enabled': False,
            'error': None,
            'has_seating_plan': False,
            'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
            'items_by_category': [
                {
                    'items': [
                        {
                            'require_voucher': False,
                            'order_min': None,
                            'max_price': None,
                            'price': {
                                'gross': '23.00',
                                'net': '19.33',
                                'tax': '3.67',
                                'name': '',
                                'rate': '19.00',
                                'includes_mixed_tax_rate': False,
                            },
                            'picture': None,
                            'has_variations': 0,
                            'allow_waitinglist': True,
                            'description': None,
                            'min_price': None,
                            'avail': [100, None],
                            'variations': [],
                            'id': self.ticket.pk,
                            'free_price': False,
                            'original_price': None,
                            'name': 'Early-bird ticket',
                            'order_max': 4,
                            'limit_one_per_user': False,
                        },
                        {
                            'require_voucher': False,
                            'order_min': None,
                            'max_price': '14.00',
                            'price': None,
                            'picture': None,
                            'has_variations': 4,
                            'allow_waitinglist': True,
                            'description': None,
                            'min_price': '12.00',
                            'avail': None,
                            'variations': [
                                {
                                    'value': 'Red',
                                    'id': self.shirt_red.pk,
                                    'original_price': None,
                                    'price': {
                                        'gross': '14.00',
                                        'net': '11.76',
                                        'tax': '2.24',
                                        'name': '',
                                        'rate': '19.00',
                                        'includes_mixed_tax_rate': False,
                                    },
                                    'description': None,
                                    'avail': [100, None],
                                    'order_max': 2,
                                },
                                {
                                    'value': 'Blue',
                                    'id': self.shirt_blue.pk,
                                    'original_price': None,
                                    'price': {
                                        'gross': '12.00',
                                        'net': '10.08',
                                        'tax': '1.92',
                                        'name': '',
                                        'rate': '19.00',
                                        'includes_mixed_tax_rate': False,
                                    },
                                    'description': None,
                                    'avail': [100, None],
                                    'order_max': 2,
                                },
                            ],
                            'id': self.shirt.pk,
                            'free_price': False,
                            'original_price': None,
                            'name': 'T-Shirt',
                            'order_max': None,
                            'limit_one_per_user': False,
                        },
                    ],
                    'description': None,
                    'id': self.category.pk,
                    'name': 'Everything',
                }
            ],
            'itemnum': 2,
            'display_add_to_cart': True,
            'cart_exists': False,
            'voucher_explanation_text': '',
        }

    def test_product_list_view_filter(self):
        response = self.client.get(
            '/%s/%s/widget/product_list?items=%s' % (self.orga.slug, self.event.slug, self.ticket.pk)
        )
        assert response['Access-Control-Allow-Origin'] == '*'
        data = json.loads(response.content.decode())
        assert data['items_by_category'] == [
            {
                'items': [
                    {
                        'require_voucher': False,
                        'order_min': None,
                        'max_price': None,
                        'price': {
                            'gross': '23.00',
                            'net': '19.33',
                            'tax': '3.67',
                            'name': '',
                            'rate': '19.00',
                            'includes_mixed_tax_rate': False,
                        },
                        'picture': None,
                        'has_variations': 0,
                        'allow_waitinglist': True,
                        'description': None,
                        'min_price': None,
                        'avail': [100, None],
                        'variations': [],
                        'id': self.ticket.pk,
                        'free_price': False,
                        'original_price': None,
                        'name': 'Early-bird ticket',
                        'order_max': 4,
                        'limit_one_per_user': False,
                    }
                ],
                'description': None,
                'id': self.category.pk,
                'name': 'Everything',
            }
        ]

        response = self.client.get(
            '/%s/%s/widget/product_list?categories=0,%s' % (self.orga.slug, self.event.slug, self.category.pk)
        )
        assert response['Access-Control-Allow-Origin'] == '*'
        data = json.loads(response.content.decode())
        assert len(data['items_by_category']) == 1

        response = self.client.get('/%s/%s/widget/product_list?categories=0' % (self.orga.slug, self.event.slug))
        assert response['Access-Control-Allow-Origin'] == '*'
        data = json.loads(response.content.decode())
        assert len(data['items_by_category']) == 0

    def test_product_list_view_with_voucher(self):
        with scopes_disabled():
            self.event.vouchers.create(product=self.ticket, code='ABCDE')
        response = self.client.get('/%s/%s/widget/product_list?voucher=ABCDE' % (self.orga.slug, self.event.slug))
        assert response['Access-Control-Allow-Origin'] == '*'
        data = json.loads(response.content.decode())
        assert data == {
            'name': '30C3',
            'date_range': f'Dec. 26th – 27th, {self.event.date_from.year} 00:00',
            'frontpage_text': '',
            'currency': 'EUR',
            'show_variations_expanded': False,
            'display_net_prices': False,
            'has_seating_plan': False,
            'vouchers_exist': True,
            'waiting_list_enabled': False,
            'error': None,
            'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
            'items_by_category': [
                {
                    'items': [
                        {
                            'require_voucher': False,
                            'order_min': None,
                            'max_price': None,
                            'price': {
                                'gross': '23.00',
                                'net': '19.33',
                                'tax': '3.67',
                                'name': '',
                                'rate': '19.00',
                                'includes_mixed_tax_rate': False,
                            },
                            'picture': None,
                            'has_variations': 0,
                            'allow_waitinglist': True,
                            'description': None,
                            'min_price': None,
                            'avail': [100, None],
                            'variations': [],
                            'id': self.ticket.pk,
                            'free_price': False,
                            'original_price': None,
                            'name': 'Early-bird ticket',
                            'order_max': 4,
                            'limit_one_per_user': False,
                        },
                    ],
                    'description': None,
                    'id': self.category.pk,
                    'name': 'Everything',
                }
            ],
            'itemnum': 1,
            'voucher_explanation_text': '',
            'display_add_to_cart': True,
            'cart_exists': False,
        }

    def test_product_list_view_with_voucher_variation_through_quota(self):
        with scopes_disabled():
            self.event.vouchers.create(quota=self.quota_shirts, code='ABCDE')
            self.quota_shirts.variations.remove(self.shirt_blue)
        response = self.client.get('/%s/%s/widget/product_list?voucher=ABCDE' % (self.orga.slug, self.event.slug))
        assert response['Access-Control-Allow-Origin'] == '*'
        data = json.loads(response.content.decode())
        assert data == {
            'name': '30C3',
            'date_range': f'Dec. 26th – 27th, {self.event.date_from.year} 00:00',
            'frontpage_text': '',
            'currency': 'EUR',
            'show_variations_expanded': False,
            'display_net_prices': False,
            'vouchers_exist': True,
            'has_seating_plan': False,
            'waiting_list_enabled': False,
            'error': None,
            'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
            'items_by_category': [
                {
                    'items': [
                        {
                            'id': self.shirt.pk,
                            'name': 'T-Shirt',
                            'picture': None,
                            'description': None,
                            'has_variations': 2,
                            'allow_waitinglist': True,
                            'require_voucher': False,
                            'order_min': None,
                            'order_max': None,
                            'limit_one_per_user': False,
                            'price': None,
                            'min_price': '14.00',
                            'max_price': '14.00',
                            'free_price': False,
                            'avail': None,
                            'original_price': None,
                            'variations': [
                                {
                                    'id': self.shirt_red.pk,
                                    'value': 'Red',
                                    'order_max': 2,
                                    'description': None,
                                    'original_price': None,
                                    'price': {
                                        'gross': '14.00',
                                        'net': '11.76',
                                        'tax': '2.24',
                                        'rate': '19.00',
                                        'name': '',
                                        'includes_mixed_tax_rate': False,
                                    },
                                    'avail': [100, None],
                                },
                            ],
                        }
                    ],
                    'description': None,
                    'id': self.category.pk,
                    'name': 'Everything',
                }
            ],
            'itemnum': 1,
            'display_add_to_cart': True,
            'voucher_explanation_text': '',
            'cart_exists': False,
        }

    def test_product_list_view_with_voucher_expired(self):
        with scopes_disabled():
            self.event.vouchers.create(
                product=self.ticket,
                code='ABCDE',
                valid_until=now() - datetime.timedelta(days=1),
            )
        response = self.client.get('/%s/%s/widget/product_list?voucher=ABCDE' % (self.orga.slug, self.event.slug))
        assert response['Access-Control-Allow-Origin'] == '*'
        data = json.loads(response.content.decode())
        assert data == {
            'name': '30C3',
            'date_range': f'Dec. 26th – 27th, {self.event.date_from.year} 00:00',
            'frontpage_text': '',
            'currency': 'EUR',
            'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
            'show_variations_expanded': False,
            'display_net_prices': False,
            'has_seating_plan': False,
            'vouchers_exist': False,
            'waiting_list_enabled': False,
            'error': 'This voucher is expired.',
            'items_by_category': [],
            'display_add_to_cart': False,
            'cart_exists': False,
            'voucher_explanation_text': '',
            'itemnum': 0,
        }

    @override_settings(COMPRESS_PRECOMPILERS=settings.COMPRESS_PRECOMPILERS_ORIGINAL)
    def test_css_customized(self):
        response = self.client.get('/%s/%s/widget/v1.css' % (self.orga.slug, self.event.slug))
        c = b''.join(response.streaming_content).decode()
        assert '#33c33c' not in c
        assert '#34c34c' not in c

        self.orga.settings.primary_color = '#33c33c'
        regenerate_organizer_css.apply(args=(self.orga.pk,))
        response = self.client.get('/%s/%s/widget/v1.css' % (self.orga.slug, self.event.slug))
        c = b''.join(response.streaming_content).decode()
        assert '#33c33c' in c
        assert '#34c34c' not in c

        self.event.settings.primary_color = '#34c34c'
        regenerate_css.apply(args=(self.event.pk,))
        response = self.client.get('/%s/%s/widget/v1.css' % (self.orga.slug, self.event.slug))
        c = b''.join(response.streaming_content).decode()
        assert '#33c33c' not in c
        assert '#34c34c' in c

    def test_js_localized(self):
        response = self.client.get('/widget/v1.en.js')
        c = response.content.decode()
        assert '%m/%d/%Y' in c
        assert '%d.%m.%Y' not in c
        response = self.client.get('/widget/v1.de.js')
        c = response.content.decode()
        assert '%m/%d/%Y' not in c
        assert '%d.%m.%Y' in c

    def test_product_list_view_with_bundle_sold_out(self):
        self.quota_shirts.size = 0
        self.quota_shirts.save()
        self.ticket.bundles.create(
            bundled_product=self.shirt,
            bundled_variation=self.shirt_blue,
            designated_price=2,
            count=1,
        )
        response = self.client.get('/%s/%s/widget/product_list' % (self.orga.slug, self.event.slug))
        assert response['Access-Control-Allow-Origin'] == '*'
        data = json.loads(response.content.decode())
        assert data['items_by_category'][0]['items'][0]['avail'] == [0, None]

    def test_product_list_view_with_bundle_mixed_tax_rate(self):
        with scopes_disabled():
            self.tr7 = self.event.tax_rules.create(rate=Decimal('7.00'))
            self.shirt.tax_rule = self.tr7
            self.shirt.require_bundling = True
            self.shirt.save()
            self.ticket.bundles.create(
                bundled_product=self.shirt,
                bundled_variation=self.shirt_blue,
                designated_price=2,
                count=1,
            )
        response = self.client.get('/%s/%s/widget/product_list' % (self.orga.slug, self.event.slug))
        assert response['Access-Control-Allow-Origin'] == '*'
        data = json.loads(response.content.decode())
        assert len(data['items_by_category'][0]['items']) == 1
        assert data['items_by_category'][0]['items'][0]['price'] == {
            'gross': '23.00',
            'net': '19.52',
            'tax': '3.48',
            'name': 'MIXED!',
            'rate': '19.00',
            'includes_mixed_tax_rate': True,
        }

    def test_subevent_list(self):
        self.event.has_subevents = True
        self.event.settings.timezone = 'Europe/Berlin'
        self.event.save()
        with freeze_time('2019-01-01 10:00:00'):
            with scopes_disabled():
                self.event.subevents.create(
                    name='Past',
                    active=True,
                    date_from=now() - datetime.timedelta(days=3),
                )
                se1 = self.event.subevents.create(name='Present', active=True, date_from=now())
                se2 = self.event.subevents.create(
                    name='Future',
                    active=True,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Disabled',
                    active=False,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Hidden',
                    active=True,
                    is_public=False,
                    date_from=now() + datetime.timedelta(days=3),
                )

            response = self.client.get('/%s/%s/widget/product_list' % (self.orga.slug, self.event.slug))
            data = json.loads(response.content.decode())
            settings.SITE_URL = 'http://example.com'
            assert data == {
                'list_type': 'list',
                'name': '30C3',
                'frontpage_text': '',
                'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
                'events': [
                    {
                        'name': 'Present',
                        'date_range': 'Jan. 1st – 2nd, 2019 11:00',
                        'availability': {
                            'color': 'none',
                            'text': '',
                            'reason': 'unknown',
                        },
                        'event_url': 'http://example.com/ccc/30c3/',
                        'subevent': se1.pk,
                        'location': '',
                    },
                    {
                        'name': 'Future',
                        'date_range': 'Jan. 4th – 5th, 2019 11:00',
                        'availability': {
                            'color': 'none',
                            'text': '',
                            'reason': 'unknown',
                        },
                        'event_url': 'http://example.com/ccc/30c3/',
                        'subevent': se2.pk,
                        'location': '',
                    },
                ],
            }

    def test_subevent_calendar(self):
        self.event.has_subevents = True
        self.event.settings.timezone = 'Europe/Berlin'
        self.event.save()
        with freeze_time('2019-01-01 10:00:00'):
            with scopes_disabled():
                self.event.subevents.create(
                    name='Past',
                    active=True,
                    date_from=now() - datetime.timedelta(days=3),
                )
                se1 = self.event.subevents.create(name='Present', active=True, date_from=now())
                se2 = self.event.subevents.create(
                    name='Future',
                    active=True,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Disabled',
                    active=False,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Hidden',
                    active=True,
                    is_public=False,
                    date_from=now() + datetime.timedelta(days=3),
                )

            response = self.client.get('/%s/%s/widget/product_list?style=calendar' % (self.orga.slug, self.event.slug))
            settings.SITE_URL = 'http://example.com'
            data = json.loads(response.content.decode())
            assert data == {
                'list_type': 'calendar',
                'date': '2019-01-01',
                'name': '30C3',
                'frontpage_text': '',
                'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
                'weeks': [
                    [
                        None,
                        {
                            'day': 1,
                            'date': '2019-01-01',
                            'events': [
                                {
                                    'name': 'Present',
                                    'time': '11:00',
                                    'continued': False,
                                    'date_range': 'Jan. 1st – 2nd, 2019 10:00',
                                    'location': '',
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'event_url': 'http://example.com/ccc/30c3/',
                                    'subevent': se1.pk,
                                }
                            ],
                        },
                        {
                            'day': 2,
                            'date': '2019-01-02',
                            'events': [
                                {
                                    'name': 'Present',
                                    'time': None,
                                    'continued': True,
                                    'date_range': 'Jan. 1st – 2nd, 2019 10:00',
                                    'location': '',
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'event_url': 'http://example.com/ccc/30c3/',
                                    'subevent': se1.pk,
                                }
                            ],
                        },
                        {'day': 3, 'date': '2019-01-03', 'events': []},
                        {
                            'day': 4,
                            'date': '2019-01-04',
                            'events': [
                                {
                                    'name': 'Future',
                                    'time': '11:00',
                                    'continued': False,
                                    'date_range': 'Jan. 4th – 5th, 2019 10:00',
                                    'location': '',
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'event_url': 'http://example.com/ccc/30c3/',
                                    'subevent': se2.pk,
                                }
                            ],
                        },
                        {
                            'day': 5,
                            'date': '2019-01-05',
                            'events': [
                                {
                                    'name': 'Future',
                                    'time': None,
                                    'continued': True,
                                    'date_range': 'Jan. 4th – 5th, 2019 10:00',
                                    'location': '',
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'event_url': 'http://example.com/ccc/30c3/',
                                    'subevent': se2.pk,
                                }
                            ],
                        },
                        {'day': 6, 'date': '2019-01-06', 'events': []},
                    ],
                    [
                        {'day': 7, 'date': '2019-01-07', 'events': []},
                        {'day': 8, 'date': '2019-01-08', 'events': []},
                        {'day': 9, 'date': '2019-01-09', 'events': []},
                        {'day': 10, 'date': '2019-01-10', 'events': []},
                        {'day': 11, 'date': '2019-01-11', 'events': []},
                        {'day': 12, 'date': '2019-01-12', 'events': []},
                        {'day': 13, 'date': '2019-01-13', 'events': []},
                    ],
                    [
                        {'day': 14, 'date': '2019-01-14', 'events': []},
                        {'day': 15, 'date': '2019-01-15', 'events': []},
                        {'day': 16, 'date': '2019-01-16', 'events': []},
                        {'day': 17, 'date': '2019-01-17', 'events': []},
                        {'day': 18, 'date': '2019-01-18', 'events': []},
                        {'day': 19, 'date': '2019-01-19', 'events': []},
                        {'day': 20, 'date': '2019-01-20', 'events': []},
                    ],
                    [
                        {'day': 21, 'date': '2019-01-21', 'events': []},
                        {'day': 22, 'date': '2019-01-22', 'events': []},
                        {'day': 23, 'date': '2019-01-23', 'events': []},
                        {'day': 24, 'date': '2019-01-24', 'events': []},
                        {'day': 25, 'date': '2019-01-25', 'events': []},
                        {'day': 26, 'date': '2019-01-26', 'events': []},
                        {'day': 27, 'date': '2019-01-27', 'events': []},
                    ],
                    [
                        {'day': 28, 'date': '2019-01-28', 'events': []},
                        {'day': 29, 'date': '2019-01-29', 'events': []},
                        {'day': 30, 'date': '2019-01-30', 'events': []},
                        {'day': 31, 'date': '2019-01-31', 'events': []},
                        None,
                        None,
                        None,
                    ],
                ],
            }

    def test_subevent_week_calendar(self):
        self.event.has_subevents = True
        self.event.settings.timezone = 'Europe/Berlin'
        self.event.save()
        with freeze_time('2019-01-01 10:00:00'):
            with scopes_disabled():
                self.event.subevents.create(
                    name='Past',
                    active=True,
                    date_from=now() - datetime.timedelta(days=3),
                )
                se1 = self.event.subevents.create(name='Present', active=True, date_from=now())
                se2 = self.event.subevents.create(
                    name='Future',
                    active=True,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Disabled',
                    active=False,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Hidden',
                    active=True,
                    is_public=False,
                    date_from=now() + datetime.timedelta(days=3),
                )

            response = self.client.get('/%s/%s/widget/product_list?style=week' % (self.orga.slug, self.event.slug))
            settings.SITE_URL = 'http://example.com'
            data = json.loads(response.content.decode())
            assert data == {
                'list_type': 'week',
                'name': '30C3',
                'frontpage_text': '',
                'week': [2019, 1],
                'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
                'days': [
                    {
                        'day_formatted': 'Mon, Dec 31st',
                        'date': '2018-12-31',
                        'events': [],
                        'today': False,
                    },
                    {
                        'day_formatted': 'Tue, Jan 1st',
                        'date': '2019-01-01',
                        'events': [
                            {
                                'name': 'Present',
                                'time': '11:00',
                                'continued': False,
                                'date_range': 'Jan. 1st – 2nd, 2019 10:00',
                                'location': '',
                                'availability': {
                                    'color': 'none',
                                    'text': '',
                                    'reason': 'unknown',
                                },
                                'event_url': 'http://example.com/ccc/30c3/',
                                'subevent': se1.pk,
                            }
                        ],
                        'today': True,
                    },
                    {
                        'day_formatted': 'Wed, Jan 2nd',
                        'date': '2019-01-02',
                        'events': [
                            {
                                'name': 'Present',
                                'time': None,
                                'continued': True,
                                'date_range': 'Jan. 1st – 2nd, 2019 10:00',
                                'location': '',
                                'availability': {
                                    'color': 'none',
                                    'text': '',
                                    'reason': 'unknown',
                                },
                                'event_url': 'http://example.com/ccc/30c3/',
                                'subevent': se1.pk,
                            }
                        ],
                        'today': False,
                    },
                    {
                        'day_formatted': 'Thu, Jan 3rd',
                        'date': '2019-01-03',
                        'events': [],
                        'today': False,
                    },
                    {
                        'day_formatted': 'Fri, Jan 4th',
                        'date': '2019-01-04',
                        'events': [
                            {
                                'name': 'Future',
                                'time': '11:00',
                                'continued': False,
                                'date_range': 'Jan. 4th – 5th, 2019 10:00',
                                'location': '',
                                'availability': {
                                    'color': 'none',
                                    'text': '',
                                    'reason': 'unknown',
                                },
                                'event_url': 'http://example.com/ccc/30c3/',
                                'subevent': se2.pk,
                            }
                        ],
                        'today': False,
                    },
                    {
                        'day_formatted': 'Sat, Jan 5th',
                        'date': '2019-01-05',
                        'events': [
                            {
                                'name': 'Future',
                                'time': None,
                                'continued': True,
                                'date_range': 'Jan. 4th – 5th, 2019 10:00',
                                'location': '',
                                'availability': {
                                    'color': 'none',
                                    'text': '',
                                    'reason': 'unknown',
                                },
                                'event_url': 'http://example.com/ccc/30c3/',
                                'subevent': se2.pk,
                            }
                        ],
                        'today': False,
                    },
                    {
                        'day_formatted': 'Sun, Jan 6th',
                        'date': '2019-01-06',
                        'events': [],
                        'today': False,
                    },
                ],
            }

    def test_event_list(self):
        self.event.has_subevents = True
        self.event.settings.timezone = 'Europe/Berlin'
        self.event.save()
        with freeze_time('2019-01-01 10:00:00'):
            with scopes_disabled():
                self.orga.events.create(
                    name='Past',
                    live=True,
                    is_public=True,
                    slug='past',
                    date_from=now() - datetime.timedelta(days=3),
                )
                self.orga.events.create(
                    name='Present',
                    live=True,
                    is_public=True,
                    slug='present',
                    date_from=now(),
                )
                self.orga.events.create(
                    name='Future',
                    live=True,
                    is_public=True,
                    slug='future',
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.orga.events.create(
                    name='Disabled',
                    live=False,
                    is_public=True,
                    slug='disabled',
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.orga.events.create(
                    name='Secret',
                    live=True,
                    is_public=False,
                    slug='secret',
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Past',
                    active=True,
                    date_from=now() - datetime.timedelta(days=3),
                )
                self.event.subevents.create(name='Present', active=True, date_from=now())
                self.event.subevents.create(
                    name='Future',
                    active=True,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Disabled',
                    active=False,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Hidden',
                    active=True,
                    is_public=False,
                    date_from=now() + datetime.timedelta(days=3),
                )

            settings.SITE_URL = 'http://example.com'
            response = self.client.get('/%s/widget/product_list' % (self.orga.slug,))
            data = json.loads(response.content.decode())
            assert data == {
                'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
                'events': [
                    {
                        'availability': {'color': 'none', 'text': 'Event series'},
                        'date_range': 'Dec. 29, 2018 – Jan. 5, 2019',
                        'event_url': 'http://example.com/ccc/30c3/',
                        'location': '',
                        'name': '30C3',
                    },
                    {
                        'availability': {
                            'color': 'none',
                            'text': '',
                            'reason': 'unknown',
                        },
                        'date_range': 'Jan. 1st – 2nd, 2019 10:00',
                        'location': '',
                        'event_url': 'http://example.com/ccc/present/',
                        'name': 'Present',
                    },
                    {
                        'availability': {
                            'color': 'none',
                            'text': '',
                            'reason': 'unknown',
                        },
                        'date_range': 'Jan. 4th – 5th, 2019 10:00',
                        'location': '',
                        'event_url': 'http://example.com/ccc/future/',
                        'name': 'Future',
                    },
                ],
                'list_type': 'list',
            }

    def test_event_calendar(self):
        self.event.has_subevents = True
        self.event.settings.timezone = 'Europe/Berlin'
        self.event.save()
        with freeze_time('2019-01-01 10:00:00'):
            with scopes_disabled():
                self.orga.events.create(
                    name='Past',
                    live=True,
                    is_public=True,
                    slug='past',
                    date_from=now() - datetime.timedelta(days=3),
                )
                self.orga.events.create(
                    name='Present',
                    live=True,
                    is_public=True,
                    slug='present',
                    date_from=now(),
                )
                self.orga.events.create(
                    name='Future',
                    live=True,
                    is_public=True,
                    slug='future',
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.orga.events.create(
                    name='Disabled',
                    live=False,
                    is_public=True,
                    slug='disabled',
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.orga.events.create(
                    name='Secret',
                    live=True,
                    is_public=False,
                    slug='secret',
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Past',
                    active=True,
                    date_from=now() - datetime.timedelta(days=3),
                )
                se1 = self.event.subevents.create(name='Present', active=True, date_from=now())
                se2 = self.event.subevents.create(
                    name='Future',
                    active=True,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Disabled',
                    active=False,
                    date_from=now() + datetime.timedelta(days=3),
                )
                self.event.subevents.create(
                    name='Hidden',
                    active=True,
                    is_public=False,
                    date_from=now() + datetime.timedelta(days=3),
                )

            response = self.client.get('/%s/widget/product_list?style=calendar' % (self.orga.slug,))
            settings.SITE_URL = 'http://example.com'
            data = json.loads(response.content.decode())
            assert data == {
                'date': '2019-01-01',
                'list_type': 'calendar',
                'poweredby': '<a href="https://eventyay.com" target="_blank" rel="noopener">powered by eventyay</a>',
                'weeks': [
                    [
                        None,
                        {
                            'date': '2019-01-01',
                            'day': 1,
                            'events': [
                                {
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'continued': False,
                                    'date_range': 'Jan. 1st – 2nd, 2019 10:00',
                                    'event_url': 'http://example.com/ccc/present/',
                                    'name': 'Present',
                                    'location': '',
                                    'subevent': None,
                                    'time': '10:00',
                                },
                                {
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'continued': False,
                                    'date_range': 'Jan. 1st – 2nd, 2019 10:00',
                                    'event_url': 'http://example.com/ccc/30c3/',
                                    'name': 'Present',
                                    'location': '',
                                    'subevent': se1.pk,
                                    'time': '11:00',
                                },
                            ],
                        },
                        {
                            'date': '2019-01-02',
                            'day': 2,
                            'events': [
                                {
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'continued': True,
                                    'date_range': 'Jan. 1st – 2nd, 2019 10:00',
                                    'event_url': 'http://example.com/ccc/present/',
                                    'name': 'Present',
                                    'location': '',
                                    'subevent': None,
                                    'time': None,
                                },
                                {
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'continued': True,
                                    'date_range': 'Jan. 1st – 2nd, 2019 10:00',
                                    'event_url': 'http://example.com/ccc/30c3/',
                                    'name': 'Present',
                                    'location': '',
                                    'subevent': se1.pk,
                                    'time': None,
                                },
                            ],
                        },
                        {'date': '2019-01-03', 'day': 3, 'events': []},
                        {
                            'date': '2019-01-04',
                            'day': 4,
                            'events': [
                                {
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'continued': False,
                                    'date_range': 'Jan. 4th – 5th, 2019 10:00',
                                    'event_url': 'http://example.com/ccc/future/',
                                    'name': 'Future',
                                    'location': '',
                                    'subevent': None,
                                    'time': '10:00',
                                },
                                {
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'continued': False,
                                    'date_range': 'Jan. 4th – 5th, 2019 10:00',
                                    'event_url': 'http://example.com/ccc/30c3/',
                                    'name': 'Future',
                                    'location': '',
                                    'subevent': se2.pk,
                                    'time': '11:00',
                                },
                            ],
                        },
                        {
                            'date': '2019-01-05',
                            'day': 5,
                            'events': [
                                {
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'continued': True,
                                    'date_range': 'Jan. 4th – 5th, 2019 10:00',
                                    'event_url': 'http://example.com/ccc/future/',
                                    'name': 'Future',
                                    'location': '',
                                    'subevent': None,
                                    'time': None,
                                },
                                {
                                    'availability': {
                                        'color': 'none',
                                        'text': '',
                                        'reason': 'unknown',
                                    },
                                    'continued': True,
                                    'date_range': 'Jan. 4th – 5th, 2019 10:00',
                                    'event_url': 'http://example.com/ccc/30c3/',
                                    'name': 'Future',
                                    'location': '',
                                    'subevent': se2.pk,
                                    'time': None,
                                },
                            ],
                        },
                        {'date': '2019-01-06', 'day': 6, 'events': []},
                    ],
                    [
                        {'date': '2019-01-07', 'day': 7, 'events': []},
                        {'date': '2019-01-08', 'day': 8, 'events': []},
                        {'date': '2019-01-09', 'day': 9, 'events': []},
                        {'date': '2019-01-10', 'day': 10, 'events': []},
                        {'date': '2019-01-11', 'day': 11, 'events': []},
                        {'date': '2019-01-12', 'day': 12, 'events': []},
                        {'date': '2019-01-13', 'day': 13, 'events': []},
                    ],
                    [
                        {'date': '2019-01-14', 'day': 14, 'events': []},
                        {'date': '2019-01-15', 'day': 15, 'events': []},
                        {'date': '2019-01-16', 'day': 16, 'events': []},
                        {'date': '2019-01-17', 'day': 17, 'events': []},
                        {'date': '2019-01-18', 'day': 18, 'events': []},
                        {'date': '2019-01-19', 'day': 19, 'events': []},
                        {'date': '2019-01-20', 'day': 20, 'events': []},
                    ],
                    [
                        {'date': '2019-01-21', 'day': 21, 'events': []},
                        {'date': '2019-01-22', 'day': 22, 'events': []},
                        {'date': '2019-01-23', 'day': 23, 'events': []},
                        {'date': '2019-01-24', 'day': 24, 'events': []},
                        {'date': '2019-01-25', 'day': 25, 'events': []},
                        {'date': '2019-01-26', 'day': 26, 'events': []},
                        {'date': '2019-01-27', 'day': 27, 'events': []},
                    ],
                    [
                        {'date': '2019-01-28', 'day': 28, 'events': []},
                        {'date': '2019-01-29', 'day': 29, 'events': []},
                        {'date': '2019-01-30', 'day': 30, 'events': []},
                        {'date': '2019-01-31', 'day': 31, 'events': []},
                        None,
                        None,
                        None,
                    ],
                ],
            }
