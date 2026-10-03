import json
from datetime import timedelta
from decimal import Decimal

import pytest
import responses
from django.db import transaction
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.api.webhooks import notify_webhooks
from eventyay.base.models import (
    Event,
    LogEntry,
    Order,
    OrderPosition,
    Organizer,
    Review,
    Submission,
    User,
)
from eventyay.base.models import Product as Item


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='Dummy', slug='dummy')


@pytest.fixture
def event(organizer):
    event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now())
    return event


@pytest.fixture
def webhook(organizer, event):
    wh = organizer.webhooks.create(enabled=True, target_url='https://google.com', all_events=False)
    wh.limit_events.add(event)
    wh.listeners.create(action_type='eventyay.event.order.placed')
    wh.listeners.create(action_type='eventyay.event.order.paid')
    return wh


@pytest.fixture
def order(event):
    o = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        locale='en',
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=Decimal('46.00'),
    )
    tr19 = event.tax_rules.create(rate=Decimal('19.00'))
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        tax_rule=tr19,
        default_price=Decimal('23.00'),
        admission=True,
    )
    OrderPosition.objects.create(
        order=o,
        product=ticket,
        variation=None,
        price=Decimal('23.00'),
        attendee_name_parts={'full_name': 'Peter'},
        positionid=1,
    )
    return o


def force_str(v):
    return v.decode() if isinstance(v, bytes) else str(v)


@pytest.fixture
def monkeypatch_on_commit(monkeypatch):
    monkeypatch.setattr('django.db.transaction.on_commit', lambda t: t())


@pytest.fixture
def cfp_webhook(organizer, event):
    webhook = organizer.webhooks.create(enabled=True, target_url='https://google.com', all_events=False)
    webhook.limit_events.add(event)
    webhook.listeners.create(action_type='eventyay.submission.accepted')
    webhook.listeners.create(action_type='eventyay.submission.rejected')
    webhook.listeners.create(action_type='eventyay.review.completed')
    webhook.listeners.create(action_type='eventyay.schedule.released')
    return webhook


@pytest.mark.django_db
@responses.activate
def test_webhook_trigger_event_specific(event, order, webhook, monkeypatch_on_commit):
    responses.add_callback(
        responses.POST,
        'https://google.com',
        callback=lambda r: (200, {}, 'ok'),
        content_type='application/json',
    )

    with transaction.atomic():
        le = order.log_action('eventyay.event.order.paid', {})
    assert len(responses.calls) == 1
    assert json.loads(force_str(responses.calls[0].request.body)) == {
        'notification_id': le.pk,
        'organizer': 'dummy',
        'event': 'dummy',
        'code': 'FOO',
        'action': 'eventyay.event.order.paid',
    }
    with scopes_disabled():
        first = webhook.calls.last()
        assert first.webhook == webhook
        assert first.target_url == 'https://google.com'
        assert first.action_type == 'eventyay.event.order.paid'
        assert not first.is_retry
        assert first.return_code == 200
        assert first.success


@pytest.mark.django_db
@responses.activate
def test_webhook_trigger_global(event, order, webhook, monkeypatch_on_commit):
    webhook.limit_events.clear()
    webhook.all_events = True
    webhook.save()
    responses.add(responses.POST, 'https://google.com', status=200)
    with transaction.atomic():
        le = order.log_action('eventyay.event.order.paid', {})
    assert len(responses.calls) == 1
    assert json.loads(force_str(responses.calls[0].request.body)) == {
        'notification_id': le.pk,
        'organizer': 'dummy',
        'event': 'dummy',
        'code': 'FOO',
        'action': 'eventyay.event.order.paid',
    }


@pytest.mark.django_db
@responses.activate
def test_webhook_trigger_global_wildcard(event, order, webhook, monkeypatch_on_commit):
    webhook.listeners.create(action_type='eventyay.event.order.changed.*')
    webhook.limit_events.clear()
    webhook.all_events = True
    webhook.save()
    responses.add(responses.POST, 'https://google.com', status=200)
    with transaction.atomic():
        le = order.log_action('eventyay.event.order.changed.item', {})
    assert len(responses.calls) == 1
    assert json.loads(force_str(responses.calls[0].request.body)) == {
        'notification_id': le.pk,
        'organizer': 'dummy',
        'event': 'dummy',
        'code': 'FOO',
        'action': 'eventyay.event.order.changed.item',
    }


@pytest.mark.django_db
@responses.activate
def test_webhook_ignore_wrong_action_type(event, order, webhook, monkeypatch_on_commit):
    responses.add(responses.POST, 'https://google.com', status=200)
    with transaction.atomic():
        order.log_action('eventyay.event.order.changed.item', {})
    assert len(responses.calls) == 0


@pytest.mark.django_db
@responses.activate
def test_webhook_ignore_disabled(event, order, webhook, monkeypatch_on_commit):
    webhook.enabled = False
    webhook.save()
    responses.add(responses.POST, 'https://google.com', status=200)
    with transaction.atomic():
        order.log_action('eventyay.event.order.changed.item', {})
    assert len(responses.calls) == 0


@pytest.mark.django_db
@responses.activate
def test_webhook_ignore_wrong_event(event, order, webhook, monkeypatch_on_commit):
    webhook.limit_events.clear()
    responses.add(responses.POST, 'https://google.com', status=200)
    with transaction.atomic():
        order.log_action('eventyay.event.order.changed.item', {})
    assert len(responses.calls) == 0


@pytest.mark.django_db
@pytest.mark.xfail(reason="retries can't be tested with celery_always_eager")
@responses.activate
def test_webhook_retry(event, order, webhook, monkeypatch_on_commit):
    responses.add(responses.POST, 'https://google.com', status=500)
    responses.add(responses.POST, 'https://google.com', status=200)
    with transaction.atomic():
        order.log_action('eventyay.event.order.paid', {})
    assert len(responses.calls) == 2
    with scopes_disabled():
        second = webhook.objects.first()
        first = webhook.objects.last()

    assert first.webhook == webhook
    assert first.target_url == 'https://google.com'
    assert first.action_type == 'eventyay.event.order.paid'
    assert not first.is_retry
    assert first.return_code == 500
    assert not first.success

    assert second.webhook == webhook
    assert second.target_url == 'https://google.com'
    assert second.action_type == 'eventyay.event.order.paid'
    assert first.is_retry
    assert first.return_code == 200
    assert first.success


@pytest.mark.django_db
@responses.activate
def test_webhook_disable_gone(event, order, webhook, monkeypatch_on_commit):
    responses.add(responses.POST, 'https://google.com', status=410)
    with transaction.atomic():
        order.log_action('eventyay.event.order.paid', {})
    assert len(responses.calls) == 1
    webhook.refresh_from_db()
    assert not webhook.enabled


@pytest.mark.django_db
@responses.activate
def test_webhook_trigger_cfp_lifecycle_events(event, cfp_webhook, monkeypatch):
    responses.add(responses.POST, 'https://google.com', status=200)
    with scope(event=event):
        submission_type = event.cfp.default_type
        accepted_submission = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title='Accepted proposal',
        )
        rejected_submission = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title='Rejected proposal',
        )
        reviewer = User.objects.create_user(email='reviewer@example.test', password='secret')

        monkeypatch.setattr('django.db.transaction.on_commit', lambda t: t())

        accepted_submission.accept()
        rejected_submission.reject()
        review = Review.objects.create(submission=accepted_submission, user=reviewer)
        review.log_action('eventyay.review.completed', person=reviewer, orga=True)
        event.release_schedule('v1')

    assert len(responses.calls) == 4
    payloads = [json.loads(force_str(call.request.body)) for call in responses.calls]
    assert [payload['action'] for payload in payloads] == [
        'eventyay.submission.accepted',
        'eventyay.submission.rejected',
        'eventyay.review.completed',
        'eventyay.schedule.released',
    ]
    assert payloads[0] == {
        'notification_id': payloads[0]['notification_id'],
        'organizer': 'dummy',
        'event': 'dummy',
        'submission': accepted_submission.code,
        'action': 'eventyay.submission.accepted',
    }
    assert payloads[1] == {
        'notification_id': payloads[1]['notification_id'],
        'organizer': 'dummy',
        'event': 'dummy',
        'submission': rejected_submission.code,
        'action': 'eventyay.submission.rejected',
    }
    assert payloads[2] == {
        'notification_id': payloads[2]['notification_id'],
        'organizer': 'dummy',
        'event': 'dummy',
        'submission': accepted_submission.code,
        'action': 'eventyay.review.completed',
    }
    assert payloads[3] == {
        'notification_id': payloads[3]['notification_id'],
        'organizer': 'dummy',
        'event': 'dummy',
        'schedule': 'v1',
        'action': 'eventyay.schedule.released',
    }
    with scopes_disabled():
        assert cfp_webhook.calls.count() == 4
        assert all(call.success for call in cfp_webhook.calls.all())


@pytest.mark.django_db
@responses.activate
def test_webhook_trigger_batch_with_invalid_entries(event, order, webhook, monkeypatch_on_commit):
    responses.add(responses.POST, 'https://google.com', status=200)

    # 1. Valid
    le_valid = LogEntry.objects.create(
        action_type='eventyay.event.order.paid',
        content_object=order,
        event=event,
    )

    # 2. No webhook type
    le_no_type = LogEntry.objects.create(
        action_type='eventyay.event.order.invalid.type',
        content_object=order,
        event=event,
    )

    # 3. No organizer (event=None, dangling reference)
    from django.contrib.contenttypes.models import ContentType

    non_existent_order_id = (Order.objects.order_by('-pk').first().pk + 1) if Order.objects.exists() else 1

    le_no_org = LogEntry.objects.create(
        action_type='eventyay.event.order.paid',
        content_type=ContentType.objects.get_for_model(Order),
        object_id=non_existent_order_id,
        event=None,
    )

    notify_webhooks([le_no_org.id, le_no_type.id, le_valid.id])

    assert len(responses.calls) == 1
    assert json.loads(force_str(responses.calls[0].request.body))['notification_id'] == le_valid.id


@pytest.mark.django_db
def test_review_webhook_payload_without_submission(event):
    from unittest.mock import MagicMock
    from eventyay.api.webhooks import ParametrizedReviewWebhookEvent

    event_type = ParametrizedReviewWebhookEvent('eventyay.review.completed', 'Review completed')
    logentry = MagicMock()
    logentry.event = event
    review = MagicMock()
    review.submission = None
    logentry.content_object = review

    assert event_type.build_payload(logentry) is None
