from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils import timezone
from django.utils.crypto import get_random_string
from django_scopes import scopes_disabled

from eventyay.base.meetup import (
    get_rsvp_product_and_quota,
    provision_meetup_event,
)
from eventyay.base.models import Event, Order, OrderPosition
from eventyay.eventyay_common.forms.event import EventCommonSettingsForm
from eventyay.presale.views.event import EventIndex, JoinOnlineVideoView
from eventyay.presale.views.meetup import (
    MEETUP_RSVP_SESSION_KEY,
    MeetupRsvpView,
)


@pytest.fixture
def meetup_event(db, organizer):
    now = timezone.now()
    event = Event.objects.create(
        organizer=organizer,
        name='Meetup Event Test',
        slug='meetup-event-test',
        date_from=now + timedelta(days=10),
        date_to=now + timedelta(days=10, hours=2),
        currency='USD',
        locale='en',
        is_public=True,
        live=True,
        email='organizer@example.com',
    )
    with scopes_disabled():
        provision_meetup_event(event)
    return event


def create_paid_order(event, product, email, name='Test Attendee', code=None):
    order_code = code or get_random_string(5).upper()
    with scopes_disabled():
        order = Order.objects.create(
            event=event,
            email=email,
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now(),
            total=Decimal('0.00'),
            sales_channel='web',
            locale='en',
            code=order_code,
        )
        pos = OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('0.00'),
            positionid=1,
            attendee_email=email,
            attendee_name_parts={'_legacy': name},
        )
        pos.save()
        return order


@pytest.mark.django_db
@scopes_disabled()
def test_settings_form_initial_and_save_updates_quota_size(meetup_event):
    """Settings form loads initial from RSVP quota and updates quota size on save."""
    product, quota = get_rsvp_product_and_quota(meetup_event)
    assert quota is not None
    quota.size = 25
    quota.save(update_fields=['size'])

    form = EventCommonSettingsForm(obj=meetup_event)
    assert form.initial['registration_limit'] == 25

    data = form.initial.copy()
    data['registration_limit'] = 50
    data.setdefault('timezone', 'UTC')
    data.setdefault('locale', 'en')
    data.setdefault('locales', ['en'])
    bound_form = EventCommonSettingsForm(data=data, obj=meetup_event)
    assert bound_form.is_valid(), bound_form.errors
    bound_form.save()

    product, quota = get_rsvp_product_and_quota(meetup_event)
    assert quota.size == 50


@pytest.mark.django_db
@scopes_disabled()
def test_presale_shows_registration_closed_when_quota_full(meetup_event, rf):
    """Presale context reports rsvp_registration_closed=True when capacity is reached."""
    product, quota = get_rsvp_product_and_quota(meetup_event)
    quota.size = 1
    quota.save(update_fields=['size'])

    request = rf.get(f'/{meetup_event.slug}/')
    request.event = meetup_event
    request.user = AnonymousUser()
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()

    view = EventIndex()
    view.request = request
    ctx = view.get_meetup_context()
    assert ctx['rsvp_registration_closed'] is False

    create_paid_order(meetup_event, product, email='first@example.com')

    ctx_after = view.get_meetup_context()
    assert ctx_after['rsvp_registration_closed'] is True


@pytest.mark.django_db
@scopes_disabled()
def test_create_rsvp_order_blocks_when_quota_exhausted(meetup_event, rf):
    """_create_rsvp_order returns None when locked availability check fails."""
    product, quota = get_rsvp_product_and_quota(meetup_event)
    quota.size = 1
    quota.save(update_fields=['size'])

    create_paid_order(meetup_event, product, email='first@example.com')

    request = rf.post(f'/{meetup_event.slug}/rsvp')
    request.event = meetup_event
    request.LANGUAGE_CODE = 'en'

    view = MeetupRsvpView()
    order = view._create_rsvp_order(
        request,
        product,
        email='second@example.com',
        name='Second Attendee',
    )
    assert order is None


@pytest.mark.django_db
@scopes_disabled()
def test_authenticated_user_authz_by_email_only(meetup_event, rf, user):
    """Authenticated users must match order by email only; cannot hijack session order code."""
    product, quota = get_rsvp_product_and_quota(meetup_event)

    victim_order = create_paid_order(
        meetup_event,
        product,
        email='other@example.com',
        name='Other User',
        code='VICTIM123',
    )

    request = rf.get(f'/{meetup_event.slug}/video')
    request.event = meetup_event
    request.user = user
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session[MEETUP_RSVP_SESSION_KEY.format(meetup_event.pk)] = victim_order.code
    request.session.save()

    view = JoinOnlineVideoView()
    view.request = request
    allowed, _, order = view.validate_access(request)
    assert allowed is False
    assert order is None

    own_order = create_paid_order(
        meetup_event,
        product,
        email=user.email,
        name=user.fullname,
        code='USER123',
    )
    allowed, _, order = view.validate_access(request)
    assert allowed is True
    assert order.code == own_order.code


@pytest.mark.django_db
@scopes_disabled()
def test_anonymous_guest_authz_by_session_order_code(meetup_event, rf):
    """Anonymous guest users authorize strictly via their session order code."""
    product, quota = get_rsvp_product_and_quota(meetup_event)

    guest_order = create_paid_order(
        meetup_event,
        product,
        email='guest@example.com',
        name='Guest User',
        code='GUEST123',
    )

    request = rf.get(f'/{meetup_event.slug}/video')
    request.event = meetup_event
    request.user = AnonymousUser()
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)

    view = JoinOnlineVideoView()
    view.request = request
    allowed, _, order = view.validate_access(request)
    assert allowed is False

    request.session[MEETUP_RSVP_SESSION_KEY.format(meetup_event.pk)] = guest_order.code
    request.session.save()
    allowed, _, order = view.validate_access(request)
    assert allowed is True
    assert order.code == guest_order.code
