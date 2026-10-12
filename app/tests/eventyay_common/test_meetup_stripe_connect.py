from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.meetup import get_rsvp_product_and_quota, provision_meetup_event
from eventyay.base.models import Event, Order, OrderPayment
from eventyay.base.payment import StripePaymentProvider
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.stripe_connect import (
    build_stripe_oauth_state,
    get_stripe_connect_credentials,
    load_stripe_oauth_state,
)
from eventyay.eventyay_common.forms.event import EventCommonSettingsForm
from eventyay.eventyay_common.views.event import EventUpdate
from eventyay.eventyay_common.views.stripe_connect import (
    EventStripeConnectAuthorizeView,
    EventStripeConnectCallbackView,
    EventStripeConnectDisconnectView,
)
from eventyay.presale.views.meetup import MeetupRsvpView


@pytest.fixture
def meetup_event(db, organizer):
    now = timezone.now()
    event = Event.objects.create(
        organizer=organizer,
        name='Meetup Connect Test',
        slug='meetup-connect-test',
        date_from=now + timedelta(days=5),
        date_to=now + timedelta(days=5, hours=2),
        currency='USD',
        locale='en',
        is_public=True,
        live=True,
        email='organizer@example.com',
    )
    with scopes_disabled():
        provision_meetup_event(event)
    return event


@pytest.fixture
def non_meetup_event(db, organizer):
    now = timezone.now()
    event = Event.objects.create(
        organizer=organizer,
        name='Regular Ticketing Event',
        slug='regular-ticketing-event',
        date_from=now + timedelta(days=5),
        date_to=now + timedelta(days=5, hours=2),
        currency='USD',
        locale='en',
        is_public=True,
        live=True,
        email='organizer@example.com',
    )
    return event


@pytest.mark.django_db
def test_stripe_connect_credentials_helper(meetup_event):
    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_connect_client_id', 'ca_platform_client_123')
    gs.settings.set('payment_stripe_connect_secret_key', 'sk_platform_live_key')
    gs.settings.set('payment_stripe_connect_publishable_key', 'pk_platform_live_key')

    creds = get_stripe_connect_credentials(meetup_event)
    assert creds['client_id'] == 'ca_platform_client_123'
    assert creds['secret_key'] == 'sk_platform_live_key'
    assert creds['publishable_key'] == 'pk_platform_live_key'
    assert creds['is_configured'] is True

    # Testmode fallback
    meetup_event.testmode = True
    gs.settings.set('payment_stripe_connect_test_secret_key', 'sk_platform_test_key')
    gs.settings.set('payment_stripe_connect_test_publishable_key', 'pk_platform_test_key')
    test_creds = get_stripe_connect_credentials(meetup_event)
    assert test_creds['secret_key'] == 'sk_platform_test_key'
    assert test_creds['publishable_key'] == 'pk_platform_test_key'


@pytest.mark.django_db
def test_stripe_oauth_state_encoding_and_validation():
    state = build_stripe_oauth_state(event_id=42, user_id=99, next_url='/settings/')
    payload = load_stripe_oauth_state(state)
    assert payload['event_id'] == 42
    assert payload['user_id'] == 99
    assert payload['next_url'] == '/settings/'


@pytest.mark.django_db
@scopes_disabled()
def test_stripe_connect_authorize_view_redirects_to_stripe(meetup_event, rf, user):
    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_connect_client_id', 'ca_platform_client_123')
    gs.settings.set('payment_stripe_connect_secret_key', 'sk_platform_live_key')

    req = rf.get('/stripe/connect/')
    req.event = meetup_event
    req.organizer = meetup_event.organizer
    req.user = user
    SessionMiddleware(lambda r: None).process_request(req)
    setattr(req, '_messages', FallbackStorage(req))

    view = EventStripeConnectAuthorizeView()
    view.setup(req)
    resp = view.get(req)

    assert resp.status_code == 302
    assert resp['Location'].startswith('https://connect.stripe.com/oauth/authorize?')
    assert 'client_id=ca_platform_client_123' in resp['Location']
    assert 'response_type=code' in resp['Location']


@pytest.mark.django_db
@scopes_disabled()
def test_stripe_connect_authorize_view_404_on_non_meetup(non_meetup_event, rf, user):
    req = rf.get('/stripe/connect/')
    req.event = non_meetup_event
    req.organizer = non_meetup_event.organizer
    req.user = user
    SessionMiddleware(lambda r: None).process_request(req)
    setattr(req, '_messages', FallbackStorage(req))

    view = EventStripeConnectAuthorizeView()
    view.setup(req)
    with pytest.raises(Http404):
        view.get(req)


@pytest.mark.django_db
@scopes_disabled()
def test_stripe_connect_callback_view_success(meetup_event, rf, user):
    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_connect_client_id', 'ca_platform_client_123')
    gs.settings.set('payment_stripe_connect_secret_key', 'sk_platform_live_key')

    state = build_stripe_oauth_state(event_id=meetup_event.pk, user_id=user.pk)
    req = rf.get(f'/stripe/callback/?code=ac_123456&state={state}')
    req.event = meetup_event
    req.organizer = meetup_event.organizer
    req.user = user
    SessionMiddleware(lambda r: None).process_request(req)
    setattr(req, '_messages', FallbackStorage(req))

    mock_oauth_resp = {
        'stripe_user_id': 'acct_test_connected_123',
        'stripe_publishable_key': 'pk_test_connected_123',
    }
    mock_acct = MagicMock()
    mock_acct.business_profile.name = 'Organizer Business'

    with (
        patch('stripe.OAuth.token', return_value=mock_oauth_resp),
        patch('stripe.Account.retrieve', return_value=mock_acct),
    ):
        view = EventStripeConnectCallbackView()
        view.setup(req)
        resp = view.get(req)

    assert resp.status_code == 302
    assert meetup_event.settings.get('payment_stripe_connect_user_id') == 'acct_test_connected_123'
    assert meetup_event.settings.get('payment_stripe_connect_publishable_key') == 'pk_test_connected_123'
    assert meetup_event.settings.get('payment_stripe_connect_account_name') == 'Organizer Business'
    assert meetup_event.settings.get('payment_stripe__enabled', as_type=bool) is True


@pytest.mark.django_db
@scopes_disabled()
def test_stripe_connect_callback_view_handles_denied(meetup_event, rf, user):
    req = rf.get('/stripe/callback/?error=access_denied&error_description=The+user+denied+your+request')
    req.event = meetup_event
    req.organizer = meetup_event.organizer
    req.user = user
    SessionMiddleware(lambda r: None).process_request(req)
    storage = FallbackStorage(req)
    setattr(req, '_messages', storage)

    view = EventStripeConnectCallbackView()
    view.setup(req)
    resp = view.get(req)

    assert resp.status_code == 302
    assert meetup_event.settings.get('payment_stripe_connect_user_id') is None


@pytest.mark.django_db
@scopes_disabled()
def test_stripe_connect_disconnect_view(meetup_event, rf, user):
    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_connect_client_id', 'ca_platform_client_123')
    gs.settings.set('payment_stripe_connect_secret_key', 'sk_platform_live_key')

    meetup_event.settings.set('payment_stripe_connect_user_id', 'acct_test_connected_123')
    meetup_event.settings.set('payment_stripe_connect_publishable_key', 'pk_test_connected_123')
    meetup_event.settings.set('payment_stripe_connect_account_name', 'Organizer Business')
    meetup_event.settings.set('payment_stripe__enabled', True)

    req = rf.post('/stripe/disconnect/')
    req.event = meetup_event
    req.organizer = meetup_event.organizer
    req.user = user
    SessionMiddleware(lambda r: None).process_request(req)
    setattr(req, '_messages', FallbackStorage(req))

    with patch('stripe.OAuth.deauthorize') as mock_deauth:
        view = EventStripeConnectDisconnectView()
        view.setup(req)
        resp = view.post(req)

    assert resp.status_code == 302
    assert meetup_event.settings.get('payment_stripe_connect_user_id') is None
    assert meetup_event.settings.get('payment_stripe_connect_publishable_key') is None
    assert meetup_event.settings.get('payment_stripe__enabled', as_type=bool) is False
    mock_deauth.assert_called_once()


@pytest.mark.django_db
@scopes_disabled()
def test_event_settings_form_validation_with_connected_account(meetup_event):
    """Paid meetup passes form validation when connected Stripe account exists without manual secrets."""
    meetup_event.settings.set('payment_stripe_connect_user_id', 'acct_test_connected_123')

    form = EventCommonSettingsForm(obj=meetup_event)
    data = form.initial.copy()
    data['registration_fee'] = Decimal('10.00')
    data.setdefault('timezone', 'UTC')
    data.setdefault('locale', 'en')
    data.setdefault('locales', ['en'])

    bound_form = EventCommonSettingsForm(data=data, obj=meetup_event)
    assert bound_form.is_valid(), bound_form.errors
    bound_form.save()
    assert meetup_event.settings.get('payment_stripe__enabled', as_type=bool) is True


@pytest.mark.django_db
@scopes_disabled()
def test_event_settings_form_validation_fails_without_keys_or_connect(meetup_event):
    """Paid meetup requires Stripe keys if no connected Stripe account is configured."""
    form = EventCommonSettingsForm(obj=meetup_event)
    data = form.initial.copy()
    data['registration_fee'] = Decimal('10.00')
    data.setdefault('timezone', 'UTC')
    data.setdefault('locale', 'en')
    data.setdefault('locales', ['en'])
    data['payment_stripe_publishable_key'] = ''
    data['payment_stripe_secret_key'] = ''
    data['payment_stripe_merchant_country'] = ''

    bound_form = EventCommonSettingsForm(data=data, obj=meetup_event)
    assert not bound_form.is_valid()
    assert 'payment_stripe_publishable_key' in bound_form.errors
    assert 'payment_stripe_secret_key' in bound_form.errors
    assert 'payment_stripe_merchant_country' in bound_form.errors


@pytest.mark.django_db
@scopes_disabled()
def test_paid_rsvp_success_with_stripe_connect(meetup_event, rf):
    """Paid RSVP charges using platform secret key and stripe_account=connected_user_id."""
    product, quota = get_rsvp_product_and_quota(meetup_event)
    product.default_price = Decimal('20.00')
    product.save(update_fields=['default_price'])

    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_connect_client_id', 'ca_platform_client_123')
    gs.settings.set('payment_stripe_connect_secret_key', 'sk_platform_live_key')

    meetup_event.settings.set('payment_stripe__enabled', True)
    meetup_event.settings.set('payment_stripe_connect_user_id', 'acct_connected_test_456')
    meetup_event.settings.set('payment_stripe_connect_publishable_key', 'pk_connected_test_456')
    meetup_event.settings.set('require_registered_account_for_tickets', False)

    req = rf.post(
        f'/{meetup_event.slug}/rsvp',
        data={
            'attendee_name': 'Connect Attendee',
            'attendee_email': 'connect_attendee@example.com',
            'stripe_token': 'tok_visa',
        },
    )
    req.event = meetup_event
    req.LANGUAGE_CODE = 'en'
    req.user = AnonymousUser()
    SessionMiddleware(lambda r: None).process_request(req)
    req.session.save()
    setattr(req, '_messages', FallbackStorage(req))

    mock_intent = MagicMock()
    mock_intent.id = 'pi_test_connect_123'
    mock_intent.status = 'succeeded'

    with patch('stripe.PaymentIntent.create', return_value=mock_intent) as mock_create:
        view = MeetupRsvpView()
        response = view.post(req)
        assert response.status_code == 302
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs['api_key'] == 'sk_platform_live_key'
        assert kwargs['stripe_account'] == 'acct_connected_test_456'
        assert kwargs['amount'] == 2000

    order = Order.objects.get(event=meetup_event, email='connect_attendee@example.com')
    assert order.status == Order.STATUS_PAID
    payment = order.payments.first()
    assert payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED


@pytest.mark.django_db
@scopes_disabled()
def test_stripe_payment_provider_is_enabled_and_executes_with_connect(meetup_event, rf):
    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_connect_secret_key', 'sk_platform_live_key')
    meetup_event.settings.set('payment_stripe_connect_user_id', 'acct_connected_provider_789')
    meetup_event.settings.set('payment_stripe__enabled', True)

    provider = StripePaymentProvider(meetup_event)
    assert provider.is_enabled is True

    order = Order.objects.create(
        event=meetup_event,
        email='buyer@example.com',
        status=Order.STATUS_PENDING,
        datetime=timezone.now(),
        expires=timezone.now(),
        total=Decimal('15.00'),
        sales_channel='web',
        locale='en',
        code='TEST1',
    )
    payment = order.payments.create(
        state=OrderPayment.PAYMENT_STATE_CREATED,
        provider='stripe',
        amount=Decimal('15.00'),
    )

    req = rf.post('/', data={'stripe_token': 'tok_visa'})
    mock_intent = MagicMock()
    mock_intent.id = 'pi_test_provider_123'
    mock_intent.status = 'succeeded'

    with patch('stripe.PaymentIntent.create', return_value=mock_intent) as mock_create:
        provider.execute_payment(req, payment)
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs['api_key'] == 'sk_platform_live_key'
        assert kwargs['stripe_account'] == 'acct_connected_provider_789'
        assert kwargs['amount'] == 1500

    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED


@pytest.mark.django_db
@scopes_disabled()
def test_event_settings_template_context_renders_stripe_connect(meetup_event, rf, user):
    """EventUpdate supplies stripe_connect_available and connect urls for meetups."""
    gs = GlobalSettingsObject()
    gs.settings.set('payment_stripe_connect_client_id', 'ca_platform_client_123')
    gs.settings.set('payment_stripe_connect_secret_key', 'sk_platform_live_key')

    req = rf.get('/settings/')
    req.event = meetup_event
    req.organizer = meetup_event.organizer
    req.user = user
    SessionMiddleware(lambda r: None).process_request(req)
    setattr(req, '_messages', FallbackStorage(req))

    view = EventUpdate()
    view.setup(req)
    view.object = meetup_event
    context = view.get_context_data()

    assert context['stripe_connect_available'] is True
    expected_url = reverse(
        'eventyay_common:event.stripe.connect',
        kwargs={'organizer': meetup_event.organizer.slug, 'event': meetup_event.slug},
    )
    assert expected_url in context['stripe_connect_url']
