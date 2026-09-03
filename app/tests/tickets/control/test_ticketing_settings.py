import pytest
from django.urls import reverse
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.forms.global_settings import TicketingSettingsForm
from decimal import Decimal


@pytest.mark.django_db
class TestTicketingSettingsCleanUp:
    def test_ticketing_settings_contains_ticketing_fields(self, staff_client):
        url = reverse('eventyay_admin:admin.global.ticketing')
        response = staff_client.get(url)
        assert response.status_code == 200

        content = response.content.decode('utf-8')
        
        # Payment Gateways MUST contain ticket payments
        assert 'id="tab-payment-gateways"' in content
        assert 'Stripe — Ticket Payments' in content
        assert 'PayPal — Ticket Payments' in content
        assert 'payment_stripe_connect_client_id' in content
        assert 'payment_stripe_connect_publishable_key' in content
        assert 'payment_paypal_connect_client_id' in content
        
        # Cart MUST be in Ticketing Settings
        assert 'id="tab-cart"' in content
        assert 'reservation_time' in content
        assert 'max_products_per_order' in content

        # Global settings tabs MUST NOT be in Ticketing
        assert 'id="tab-meta-data"' not in content
        assert 'id="tab-event-creation"' not in content
        assert 'id="tab-email"' not in content

    def test_ticketing_settings_save(self, staff_client):
        url = reverse('eventyay_admin:admin.global.ticketing')
        response = staff_client.post(url, {
            'payment_stripe_connect_app_fee_percent': '10.50',
            'reservation_time': '45',
            'max_products_per_order': '5',
            'email_vendor': 'smtp',  # Some other fields to satisfy form if they accidentally bleed over? No, just these.
        })
        assert response.status_code == 302
        assert response['Location'] == reverse('eventyay_admin:admin.global.ticketing')

        gs = GlobalSettingsObject()
        assert gs.settings.get('payment_stripe_connect_app_fee_percent', as_type=Decimal) == Decimal('10.50')
        assert gs.settings.get('reservation_time', as_type=int) == 45
        assert gs.settings.get('max_products_per_order', as_type=int) == 5


@pytest.mark.django_db
class TestTicketingFormStructures:
    def test_ticketing_settings_form_fields(self):
        form = TicketingSettingsForm()
        expected_fields = {
            'payment_stripe_connect_client_id',
            'payment_stripe_connect_publishable_key',
            'payment_stripe_connect_secret_key',
            'payment_stripe_connect_test_publishable_key',
            'payment_stripe_connect_test_secret_key',
            'payment_stripe_connect_app_fee_percent',
            'payment_stripe_connect_app_fee_min',
            'payment_stripe_connect_app_fee_max',
            'payment_paypal_connect_client_id',
            'payment_paypal_connect_secret_key',
            'payment_paypal_connect_endpoint',
            'reservation_time',
            'max_products_per_order',
        }
        assert set(form.fields.keys()) == expected_fields
        groups = [g[0] for g in form.field_groups]
        assert groups == ['payment-gateways', 'cart']
