import pytest
from decimal import Decimal
from django.test import Client
from django.urls import resolve, reverse

from eventyay.base.models import InvoiceVoucher, User
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.forms.global_settings import (
    GlobalBusinessSettingsForm,
    GlobalSettingsForm,
)
from eventyay.control.navigation import get_admin_navigation


@pytest.fixture
def admin_user():
    return User.objects.create_superuser('admin@example.com', 'adminpassword')


@pytest.fixture
def staff_client(client, admin_user):
    client.force_login(admin_user)
    # Start sudo staff session required by AdministratorPermissionRequiredMixin
    session = client.session
    session['staff_session'] = admin_user.pk
    session.save()
    from eventyay.base.models.auth import StaffSession
    StaffSession.objects.create(user=admin_user, session_key=session.session_key)
    return client


@pytest.mark.django_db
class TestBusinessSettingsNavigation:
    def test_navigation_structure_and_order(self, rf, admin_user):
        request = rf.get('/admin/global/settings/')
        request.user = admin_user
        request.resolver_match = resolve('/admin/global/settings/')

        nav = get_admin_navigation(request)
        global_settings = next((item for item in nav if str(item.get('label')) == 'Global settings'), None)
        assert global_settings is not None

        child_labels = [str(child['label']) for child in global_settings['children']]
        assert 'Business' in child_labels
        assert 'Settings' in child_labels
        assert 'System information' in child_labels

        # Verify exact ordering: Settings, Business, System information, Pages, ...
        settings_idx = child_labels.index('Settings')
        business_idx = child_labels.index('Business')
        sysinfo_idx = child_labels.index('System information')
        assert settings_idx < business_idx < sysinfo_idx

        # Standalone Vouchers must NOT be present in nav
        top_labels = [str(item.get('label')) for item in nav]
        assert 'Vouchers' not in top_labels

    def test_navigation_active_states(self, rf, admin_user):
        # When visiting Business page
        request = rf.get('/admin/global/business/')
        request.user = admin_user
        request.resolver_match = resolve('/admin/global/business/')

        nav = get_admin_navigation(request)
        global_settings = next((item for item in nav if str(item.get('label')) == 'Global settings'), None)
        assert global_settings is not None
        assert global_settings['active'] is True

        business_item = next((c for c in global_settings['children'] if str(c['label']) == 'Business'), None)
        assert business_item is not None
        assert business_item['active'] is True

        settings_item = next((c for c in global_settings['children'] if str(c['label']) == 'Settings'), None)
        assert settings_item is not None
        assert settings_item['active'] is False


@pytest.mark.django_db
class TestBusinessSettingsPermissions:
    def test_anonymous_redirected_to_login(self, client):
        url = reverse('eventyay_admin:admin.global.business')
        response = client.get(url)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_non_staff_forbidden(self, client):
        user = User.objects.create_user('regular@example.com', 'dummy')
        client.force_login(user)
        url = reverse('eventyay_admin:admin.global.business')
        response = client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestBusinessSettingsView:
    def test_business_page_renders_all_tabs(self, staff_client):
        url = reverse('eventyay_admin:admin.global.business')
        response = staff_client.get(url)
        assert response.status_code == 200

        content = response.content.decode('utf-8')
        # Check page heading and 4 tab fieldset IDs exist
        assert '<h1>Business Settings</h1>' in content
        assert 'id="tab-organizer_billing"' in content
        assert 'id="tab-ticket_fee"' in content
        assert 'id="tab-billing_validation"' in content
        assert 'id="tab-event_vouchers"' in content

        # Check Organizer Billing texts and fields
        assert 'Stripe — Organizer Billing' in content
        assert 'This configuration is used for organiser billing and platform fee collection.' in content
        assert 'payment_stripe_publishable_key' in content
        assert 'payment_stripe_secret_key' in content
        assert 'payment_stripe_test_publishable_key' in content
        assert 'payment_stripe_test_secret_key' in content
        assert 'stripe_webhook_secret_key' in content

        # Check Ticket Fee and Billing Validation fields
        assert 'ticket_fee_percentage' in content
        assert 'billing_validation' in content

        # Check Event Vouchers texts and action
        assert 'Event vouchers are used by platform admins to waive or reduce Eventyay platform fees' in content
        assert reverse('eventyay_admin:admin.vouchers.add') in content

    def test_business_page_renders_vouchers_table(self, staff_client):
        InvoiceVoucher.objects.create(
            code='TESTVOUCHER2026',
            max_usages=10,
            redeemed=2,
            price_mode='percent',
            value=Decimal('20.00'),
        )
        url = reverse('eventyay_admin:admin.global.business')
        response = staff_client.get(url)
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'TESTVOUCHER2026' in content
        assert '2 / 10' in content

    def test_business_settings_save(self, staff_client):
        url = reverse('eventyay_admin:admin.global.business')
        post_data = {
            'payment_stripe_publishable_key': 'pk_live_business_test_123',
            'payment_stripe_secret_key': 'sk_live_business_test_123',
            'payment_stripe_test_publishable_key': 'pk_test_business_test_123',
            'payment_stripe_test_secret_key': 'sk_test_business_test_123',
            'stripe_webhook_secret_key': 'whsec_business_test_123',
            'ticket_fee_percentage': '3.50',
            'billing_validation': 'on',
        }
        response = staff_client.post(url, post_data)
        assert response.status_code == 302
        assert response['Location'] == reverse('eventyay_admin:admin.global.business')

        gs = GlobalSettingsObject()
        assert gs.settings.get('payment_stripe_publishable_key') == 'pk_live_business_test_123'
        assert gs.settings.get('ticket_fee_percentage', as_type=Decimal) == Decimal('3.50')
        assert gs.settings.get('billing_validation', as_type=bool) is True

    def test_vouchers_url_redirects_to_business_tab(self, staff_client):
        url = reverse('eventyay_admin:admin.vouchers')
        response = staff_client.get(url)
        assert response.status_code == 302
        assert response['Location'] == f"{reverse('eventyay_admin:admin.global.business')}#tab-event_vouchers"


@pytest.mark.django_db
class TestGlobalSettingsCleanUp:
    def test_global_settings_does_not_contain_moved_fields(self, staff_client):
        url = reverse('eventyay_admin:admin.global.settings')
        response = staff_client.get(url)
        assert response.status_code == 200

        content = response.content.decode('utf-8')
        # Stripe Organizer Billing should NOT be in Global Settings
        assert 'Stripe — Organizer Billing' not in content
        assert 'payment_stripe_publishable_key' not in content
        assert 'payment_stripe_secret_key' not in content
        assert 'stripe_webhook_secret_key' not in content

        # Ticket Fee and Billing Validation tabs should NOT be in Global Settings
        assert 'id="tab-ticket_fee"' not in content
        assert 'id="tab-billing_validation"' not in content
        assert 'id="tab-organizer_billing"' not in content

        # Payment Gateways MUST still contain ticket payments
        assert 'id="tab-payment_gateways"' in content
        assert 'Stripe — Ticket Payments' in content
        assert 'PayPal — Ticket Payments' in content
        assert 'payment_stripe_connect_client_id' in content
        assert 'payment_stripe_connect_publishable_key' in content
        assert 'payment_paypal_connect_client_id' in content

    def test_global_settings_redirects_for_legacy_tabs(self, staff_client):
        url = reverse('eventyay_admin:admin.global.settings')

        for tab in ('organizer_billing', 'ticket_fee', 'billing_validation', 'vouchers', 'event_vouchers'):
            expected_tab = 'event_vouchers' if tab == 'vouchers' else tab
            response = staff_client.get(f'{url}?tab={tab}')
            assert response.status_code == 302
            assert response['Location'] == f"{reverse('eventyay_admin:admin.global.business')}#tab-{expected_tab}"


@pytest.mark.django_db
class TestFormStructures:
    def test_global_business_settings_form_fields(self):
        form = GlobalBusinessSettingsForm()
        expected_fields = {
            'payment_stripe_publishable_key',
            'payment_stripe_secret_key',
            'payment_stripe_test_publishable_key',
            'payment_stripe_test_secret_key',
            'stripe_webhook_secret_key',
            'ticket_fee_percentage',
            'billing_validation',
        }
        assert set(form.fields.keys()) == expected_fields
        groups = [g[0] for g in form.field_groups]
        assert groups == ['organizer_billing', 'ticket_fee', 'billing_validation']

    def test_global_settings_form_does_not_contain_business_fields(self):
        form = GlobalSettingsForm()
        business_fields = {
            'payment_stripe_publishable_key',
            'payment_stripe_secret_key',
            'payment_stripe_test_publishable_key',
            'payment_stripe_test_secret_key',
            'stripe_webhook_secret_key',
            'ticket_fee_percentage',
            'billing_validation',
        }
        for field in business_fields:
            assert field not in form.fields
        groups = [g[0] for g in form.field_groups]
        assert 'ticket_fee' not in groups
        assert 'billing_validation' not in groups
