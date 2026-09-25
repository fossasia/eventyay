import datetime
import json

import pytest
from django.test import override_settings
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Checkin,
    CheckinList,
    Event,
    Order,
    OrderPayment,
    OrderPosition,
    Organizer,
    OrganizerFollower,
    Product,
    QueuedMail,
    Submission,
    SubmissionStates,
    SubmissionType,
    Team,
)
from eventyay.eventyay_common.views.organizer_analytics import OrganizerAnalyticsView


@pytest.mark.django_db
def test_to_date_helpers():
    assert OrganizerAnalyticsView._to_date(None) is None
    assert OrganizerAnalyticsView._to_date("") is None

    dt = datetime.datetime(2026, 7, 20, 12, 0, 0)
    assert OrganizerAnalyticsView._to_date(dt) == datetime.date(2026, 7, 20)

    d = datetime.date(2026, 7, 20)
    assert OrganizerAnalyticsView._to_date(d) == d

    assert OrganizerAnalyticsView._to_date("2026-07-20 12:00:00") == datetime.date(2026, 7, 20)
    assert OrganizerAnalyticsView._to_date("invalid-date") is None

    assert OrganizerAnalyticsView._to_iso_date(None) == ""
    assert OrganizerAnalyticsView._to_iso_date(dt) == "2026-07-20"


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL="https://testserver")
def test_organizer_analytics_view_permissions(organizer_client, client, organizer):
    with pytest.raises(NoReverseMatch):
        reverse('eventyay_common:organizer.analytics', kwargs={'organizer': organizer.slug})

    dashboard_url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})

    response = organizer_client.get(dashboard_url)
    assert response.status_code == 200
    assert "Organizer Dashboard" in response.content.decode()

    client.logout()
    response = client.get(dashboard_url)
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL="https://testserver")
def test_organizer_analytics_view_context(organizer_client, organizer, event, user, team):
    now = timezone.now()

    with scopes_disabled():
        team.can_change_submissions = True
        team.can_checkin_orders = True
        team.save()

        item_obj = Product.objects.create(
            event=event,
            name='Ticket',
            default_price=50.0,
        )
        order = Order.objects.create(
            event=event,
            code='TEST1',
            status=Order.STATUS_PAID,
            datetime=now,
            total=50.0,
            locale='en',
        )
        OrderPayment.objects.create(
            order=order,
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=50.0,
            payment_date=now,
        )
        op = OrderPosition.objects.create(
            order=order,
            price=50.0,
            product=item_obj,
        )

        sub_type = SubmissionType.objects.create(
            event=event,
            name="Talk",
        )
        Submission.objects.create(
            event=event,
            title='My Talk Proposal',
            state=SubmissionStates.SUBMITTED,
            submission_type=sub_type,
        )

        cl = CheckinList.objects.create(
            event=event,
            name='Main Entrance',
        )
        Checkin.objects.create(
            position=op,
            list=cl,
            type=Checkin.TYPE_ENTRY,
            datetime=now,
        )

        QueuedMail.objects.create(
            event=event,
            to="attendee@example.com",
            subject="Welcome",
            text="Welcome to the event!",
        )

        OrganizerFollower.objects.create(
            organizer=organizer,
            user=user,
        )

    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    response = organizer_client.get(url)
    assert response.status_code == 200, f"Redirected to {response.get('Location') or 'unknown'}"

    ctx = response.context

    assert ctx['follower_total'] == 1
    assert ctx['has_followers'] is True
    assert 'followers_weekly_json' in ctx
    assert 'followers_monthly_json' in ctx

    assert 'email_engagement_rows' in ctx
    assert len(ctx['email_engagement_rows']) == 1
    assert ctx['email_engagement_rows'][0]['queued'] == 1
    assert "{" not in ctx['email_engagement_rows'][0]['event_name']
    assert ctx['has_email_engagement'] is True

    assert 'attendance_events' in ctx
    assert len(ctx['attendance_events']) == 1
    assert ctx['has_attendance'] is True
    assert 'attendance_over_time_json' in ctx

    assert ctx['has_orders'] is True
    assert 'orders_over_time_json' in ctx
    assert 'orders_by_status_json' in ctx
    assert 'revenue_over_time_json' in ctx
    assert len(ctx['top_events']) == 1
    assert ctx['top_events'][0]['name'] == str(event.name)
    assert "{" not in ctx['top_events'][0]['name']

    assert ctx['has_proposals'] is True
    assert 'proposals_by_state_json' in ctx
    assert 'proposals_over_time_json' in ctx
    assert len(ctx['pending_proposal_events']) == 1

    assert ctx['show_checkins'] is True
    assert 'checkin_rate_json' in ctx
    assert 'checkins_over_time_json' in ctx


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL="https://testserver")
def test_organizer_analytics_scoped_permissions(organizer, user, client):
    with scopes_disabled():
        event_allowed = Event.objects.create(
            organizer=organizer,
            name="Allowed Event",
            slug="allowed",
            date_from=timezone.now(),
        )
        event_denied = Event.objects.create(
            organizer=organizer,
            name="Denied Event",
            slug="denied",
            date_from=timezone.now(),
        )

        team_orders = Team.objects.create(
            organizer=organizer,
            name="Orders Viewers",
            all_events=False,
            can_view_orders=True,
        )
        team_orders.limit_events.add(event_allowed)
        team_orders.members.add(user)

    client.force_login(user)
    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    response = client.get(url)
    assert response.status_code == 200, f"Redirected to {response.get('Location') or 'unknown'}"

    ctx = response.context
    attendance_events = ctx['attendance_events']
    event_ids = [e['id'] for e in attendance_events]
    assert event_allowed.pk in event_ids
    assert event_denied.pk not in event_ids


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL="https://testserver")
def test_organizer_analytics_empty_state_and_attendance_filter(organizer_client, organizer, event):
    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})

    response = organizer_client.get(url)
    assert response.status_code == 200
    ctx = response.context
    assert ctx['has_followers'] is False
    assert ctx['has_email_engagement'] is False

    url_filtered = f"{url}?attendance_event={event.pk}"
    response_filtered = organizer_client.get(url_filtered)
    assert response_filtered.status_code == 200
    assert response_filtered.context['attendance_selected_event_id'] == event.pk


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL="https://testserver")
def test_email_engagement_requires_cfp_permission(organizer, user, client):
    with scopes_disabled():
        event = Event.objects.create(
            organizer=organizer,
            name="Test Event",
            slug="test-email-perm",
            date_from=timezone.now(),
        )

        orders_team = Team.objects.create(
            organizer=organizer,
            name="Orders Only",
            all_events=True,
            can_view_orders=True,
            can_change_submissions=False,
        )
        orders_team.members.add(user)

        QueuedMail.objects.create(
            event=event,
            to="speaker@example.com",
            subject="Your proposal was accepted",
            text="Congratulations!",
        )

    client.force_login(user)
    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    response = client.get(url)
    assert response.status_code == 200
    ctx = response.context

    assert ctx['has_email_engagement'] is False
    assert ctx['email_engagement_rows'] == []

    with scopes_disabled():
        orders_team.can_change_submissions = True
        orders_team.save()

    response = client.get(url + '?refresh=1')
    assert response.status_code == 200
    ctx = response.context

    assert ctx['has_email_engagement'] is True
    assert len(ctx['email_engagement_rows']) == 1
    assert ctx['email_engagement_rows'][0]['queued'] == 1


def _attendance_totals(ctx):
    series = json.loads(ctx['attendance_over_time_json'])
    return sum(point['orders'] for point in series)


def create_event_with_orders(organizer: Organizer, slug: str, currency: str, order_count: int) -> Event:
    event = Event.objects.create(
        organizer=organizer,
        name=slug.upper(),
        slug=slug,
        currency=currency,
        date_from=timezone.now(),
    )
    for index in range(order_count):
        Order.objects.create(
            event=event,
            code=f'{slug.upper()}{index:02d}',
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            total=10,
            locale='en',
        )
    return event


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL='https://testserver')
def test_attendance_selector_survives_empty_event_selection(organizer_client, organizer, event):
    with scopes_disabled():
        empty_event = Event.objects.create(
            organizer=organizer,
            name='Empty Event',
            slug='empty',
            date_from=timezone.now(),
        )
        Order.objects.create(
            event=event,
            code='ATT01',
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            total=10,
            locale='en',
        )

    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    response = organizer_client.get(f'{url}?attendance_event={empty_event.pk}')
    assert response.status_code == 200
    ctx = response.context
    assert ctx['has_attendance'] is True
    assert ctx['attendance_selected_event_id'] == empty_event.pk
    assert _attendance_totals(ctx) == 0
    content = response.content.decode()
    assert 'id="attendance-event"' in content
    assert f'<option value="{empty_event.pk}" selected>' in content

    response = organizer_client.get(url)
    assert response.context['attendance_selected_event_id'] == ''
    assert _attendance_totals(response.context) == 1


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL='https://testserver')
def test_attendance_inaccessible_event_falls_back_to_all_events(organizer, user, client):
    with scopes_disabled():
        event_allowed = Event.objects.create(
            organizer=organizer,
            name='Allowed Event',
            slug='allowed',
            date_from=timezone.now(),
        )
        event_denied = Event.objects.create(
            organizer=organizer,
            name='Denied Event',
            slug='denied',
            date_from=timezone.now(),
        )
        for code, ev in (('ALLOW1', event_allowed), ('DENY01', event_denied)):
            Order.objects.create(
                event=ev,
                code=code,
                status=Order.STATUS_PAID,
                datetime=timezone.now(),
                total=10,
                locale='en',
            )
        team = Team.objects.create(
            organizer=organizer,
            name='Orders Viewers',
            all_events=False,
            can_view_orders=True,
        )
        team.limit_events.add(event_allowed)
        team.members.add(user)

    client.force_login(user)
    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    for requested in (event_denied.pk, 'not-an-id'):
        response = client.get(f'{url}?attendance_event={requested}')
        assert response.status_code == 200
        ctx = response.context
        assert ctx['attendance_selected_event_id'] == ''
        assert _attendance_totals(ctx) == 1
        assert 'Denied Event' not in response.content.decode()


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL='https://testserver')
def test_top_events_include_currency_outside_overall_top_ten(organizer_client, organizer):
    with scopes_disabled():
        usd_events = [create_event_with_orders(organizer, f'usd{index:02d}', 'USD', 3) for index in range(12)]
        inr_event = create_event_with_orders(organizer, 'inrevent', 'INR', 1)

    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    response = organizer_client.get(f'{url}?refresh=1')
    assert response.status_code == 200
    ctx = response.context
    top_events = ctx['top_events']

    overall = [event for event in top_events if event['in_overall_top']]
    assert [event['slug'] for event in overall] == [event.slug for event in usd_events[:10]]
    assert [event['slug'] for event in top_events if event['currency'] == 'INR'] == [inr_event.slug]
    assert len([event for event in top_events if event['currency'] == 'USD']) == 10
    assert ctx['top_event_currencies'] == ['INR', 'USD']

    content = response.content.decode()
    assert 'id="top-events-currency"' in content
    assert '<tr data-currency="INR" hidden>' in content
    assert content.count('<tr data-currency="USD" data-od-overall>') == 10


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL='https://testserver')
def test_top_events_limit_each_currency_to_ten(organizer_client, organizer):
    with scopes_disabled():
        for index in range(11):
            create_event_with_orders(organizer, f'usd{index:02d}', 'USD', 2)
            create_event_with_orders(organizer, f'eur{index:02d}', 'EUR', 1)

    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    top_events = organizer_client.get(f'{url}?refresh=1').context['top_events']

    assert len([event for event in top_events if event['currency'] == 'USD']) == 10
    assert len([event for event in top_events if event['currency'] == 'EUR']) == 10
    assert len([event for event in top_events if event['in_overall_top']]) == 10
    assert all(event['currency'] == 'USD' for event in top_events if event['in_overall_top'])
