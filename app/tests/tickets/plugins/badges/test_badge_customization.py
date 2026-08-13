import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django_scopes import scopes_disabled
from rest_framework.test import APIClient

from eventyay.base.models import CachedTicket, Event, Order, OrderPosition, Organizer, Product, Team
from eventyay.plugins.badges.models import BadgeProduct
from eventyay.plugins.badges.utils import (
    BADGE_TICKET_PROVIDER,
    get_badge_bundle_option_choices,
    get_badge_field_overrides,
    save_badge_customization,
    validate_badge_field_overrides,
)


@pytest.fixture
def badge_customization_env():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='CCC', slug='ccc')
        event = Event.objects.create(
            organizer=organizer,
            name='30C3',
            slug='30c3',
            plugins='eventyay.plugins.badges',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
        )
        product = Product.objects.create(
            event=event,
            name='Standard',
            default_price=0,
            admission=True,
            position=1,
        )
        order = Order.objects.create(
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PAID,
            datetime=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
            expires=datetime.datetime(2014, 1, 26, tzinfo=datetime.timezone.utc),
            total=0,
        )
        position = OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('0.00'),
            attendee_name_parts={'full_name': 'Ada Lovelace', '_scheme': 'full'},
            secret='secret-badge-1',
        )
        layout = event.badge_layouts.create(
            name='Layout 1',
            default=True,
            allow_customization=True,
            allow_badge_editing=True,
        )
        layout.ask_user_fields_data = ['attendee_name']
        layout.save(update_fields=['ask_user_fields'])
        yield event, order, position, product, layout


def _api_client_for_event(event):
    team = Team.objects.create(
        organizer=event.organizer,
        name='Badge API',
        can_view_orders=True,
        can_change_orders=True,
        all_events=True,
    )
    token = team.tokens.create(name='badge')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.token)
    return client


@pytest.mark.django_db
def test_validate_overrides_rejects_non_ask_user_fields(badge_customization_env):
    event, order, position, product, layout = badge_customization_env

    with pytest.raises(ValidationError, match='Invalid badge field keys'):
        validate_badge_field_overrides(
            event,
            position,
            {'attendee_company': 'FOSSASIA'},
        )


@pytest.mark.django_db
def test_validate_overrides_rejects_when_editing_disabled(badge_customization_env):
    event, order, position, product, layout = badge_customization_env
    layout.allow_badge_editing = False
    layout.save(update_fields=['allow_badge_editing'])

    with pytest.raises(ValidationError, match='Badge editing is not allowed'):
        validate_badge_field_overrides(event, position, {'attendee_name': 'Grace'})


@pytest.mark.django_db
def test_validate_overrides_rejects_when_customization_disabled(badge_customization_env):
    event, order, position, product, layout = badge_customization_env
    layout.allow_customization = False
    layout.save(update_fields=['allow_customization'])

    with pytest.raises(ValidationError, match='Badge customization is not allowed'):
        validate_badge_field_overrides(event, position, {'attendee_name': 'Grace'})


@pytest.mark.django_db
def test_validate_overrides_accepts_bundle_option_fields(badge_customization_env):
    event, order, position, product, layout = badge_customization_env
    choices = get_badge_bundle_option_choices(event, position)
    assert [key for key, _label in choices] == ['attendee_name']

    normalized = validate_badge_field_overrides(event, position, {'attendee_name': ' Grace '})
    assert normalized == {'attendee_name': 'Grace'}


@pytest.mark.django_db
def test_save_overrides_invalidates_cached_badge(badge_customization_env):
    event, order, position, product, layout = badge_customization_env
    CachedTicket.objects.create(
        order_position=position,
        provider=BADGE_TICKET_PROVIDER,
        type='application/pdf',
        extension='.pdf',
        file='badges/cached.pdf',
    )
    assert CachedTicket.objects.filter(order_position=position, provider=BADGE_TICKET_PROVIDER).exists()

    changed = save_badge_customization(position, field_overrides={'attendee_name': 'Grace Hopper'})
    assert changed is True
    assert get_badge_field_overrides(position) == {'attendee_name': 'Grace Hopper'}
    assert not CachedTicket.objects.filter(order_position=position, provider=BADGE_TICKET_PROVIDER).exists()


@pytest.mark.django_db
def test_badge_download_layout_override_returns_pdf(badge_customization_env, monkeypatch):
    event, order, position, product, layout = badge_customization_env
    alt_layout = event.badge_layouts.create(name='Alt', default=False)
    client = _api_client_for_event(event)

    monkeypatch.setattr(
        'eventyay.plugins.badges.providers.BadgeOutputProvider.generate',
        lambda self, op, layout=None: (
            'badge.pdf',
            'application/pdf',
            b'%PDF-override-' + str(layout.pk if layout else 0).encode(),
        ),
    )

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/orderpositions/{}/download/badge/?layout={}'.format(
            event.organizer.slug,
            event.slug,
            position.pk,
            alt_layout.pk,
        )
    )
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('application/pdf')
    assert resp.content.startswith(b'%PDF-override-')
    assert str(alt_layout.pk).encode() in resp.content


@pytest.mark.django_db
def test_badge_download_rejects_unknown_layout(badge_customization_env):
    event, order, position, product, layout = badge_customization_env
    client = _api_client_for_event(event)

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/orderpositions/{}/download/badge/?layout=999999'.format(
            event.organizer.slug,
            event.slug,
            position.pk,
        )
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_badge_download_allows_unpaid_when_plugin_enabled(badge_customization_env):
    event, order, position, product, layout = badge_customization_env
    order.status = Order.STATUS_PENDING
    order.save(update_fields=['status'])
    client = _api_client_for_event(event)

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/orderpositions/{}/download/badge/'.format(
            event.organizer.slug,
            event.slug,
            position.pk,
        )
    )
    # Badge downloads intentionally bypass the unpaid-order gate when the plugin is on.
    assert resp.status_code == 409


@pytest.mark.django_db
def test_badge_download_allows_generate_ticket_false(badge_customization_env):
    event, order, position, product, layout = badge_customization_env
    product.generate_tickets = False
    product.save(update_fields=['generate_tickets'])
    assert position.generate_ticket is False
    client = _api_client_for_event(event)

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/orderpositions/{}/download/badge/'.format(
            event.organizer.slug,
            event.slug,
            position.pk,
        )
    )
    assert resp.status_code == 409


@pytest.mark.django_db
def test_badge_download_still_attempted_without_layout_assignment(badge_customization_env):
    event, order, position, product, layout = badge_customization_env
    BadgeProduct.objects.create(product=product, layout=None)
    client = _api_client_for_event(event)

    resp = client.get(
        '/api/v1/organizers/{}/events/{}/orderpositions/{}/download/badge/'.format(
            event.organizer.slug,
            event.slug,
            position.pk,
        )
    )
    # Eligibility is not enforced on the download endpoint today; generation is async.
    assert resp.status_code == 409


@pytest.mark.django_db
def test_patch_badge_field_overrides_via_api(badge_customization_env):
    event, order, position, product, layout = badge_customization_env
    client = _api_client_for_event(event)

    url = '/api/v1/organizers/{}/events/{}/orderpositions/{}/'.format(
        event.organizer.slug,
        event.slug,
        position.pk,
    )
    resp = client.patch(url, {'badge_field_overrides': {'attendee_company': 'Nope'}}, format='json')
    assert resp.status_code == 400

    resp = client.patch(url, {'badge_field_overrides': {'attendee_name': 'Grace Hopper'}}, format='json')
    assert resp.status_code == 200
    assert resp.data['badge_customization']['field_overrides'] == {'attendee_name': 'Grace Hopper'}
    assert resp.data['badge_customization']['allow_badge_editing'] is True

    position.refresh_from_db()
    assert get_badge_field_overrides(position) == {'attendee_name': 'Grace Hopper'}
