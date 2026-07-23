import datetime
import pytest
from django.urls import reverse
from django.utils import timezone
from django.test import override_settings
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Checkin,
    CheckinList,
    Event,
    Product,
    Order,
    OrderPayment,
    OrderPosition,
    OrganizerFollower,
    QueuedMail,
    Submission,
    SubmissionStates,
    SubmissionType,
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
    url = reverse('eventyay_common:organizer.analytics', kwargs={'organizer': organizer.slug})

    response = organizer_client.get(url)
    assert response.status_code == 200, f"Redirected to {response.get('Location') or 'unknown'}"
    assert "analytics-page" in response.content.decode()

    client.logout()
    response = client.get(url)
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

    url = reverse('eventyay_common:organizer.analytics', kwargs={'organizer': organizer.slug})
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
    from eventyay.base.models import Team

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
    url = reverse('eventyay_common:organizer.analytics', kwargs={'organizer': organizer.slug})
    response = client.get(url)
    assert response.status_code == 200, f"Redirected to {response.get('Location') or 'unknown'}"

    ctx = response.context
    attendance_events = ctx['attendance_events']
    event_ids = [e['id'] for e in attendance_events]
    assert event_allowed.pk in event_ids
    assert event_denied.pk not in event_ids
