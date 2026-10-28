from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.dispatch import Signal
from django.utils.timezone import now
from django_scopes import scope

from eventyay.api import webhooks
from eventyay.base import entitlements
from eventyay.base.models import Event, LogEntry, Organizer


@pytest.mark.django_db
def test_webhooks_check_entitlement_at_enqueue_and_delivery(monkeypatch):
    organizer = Organizer.objects.create(name='Webhook plan', slug='webhook-plan')
    event = Event.objects.create(organizer=organizer, name='Event', slug='event', date_from=now())
    signal = Signal()
    monkeypatch.setattr(entitlements, 'entitlement_check', signal)
    allowed = False

    def receiver(sender, capability, event, **kwargs):
        assert sender == organizer
        assert capability == 'api.webhooks'
        return allowed

    signal.connect(receiver, weak=False)
    event_type = SimpleNamespace(
        action_type='eventyay.event.order.paid', build_payload=Mock(return_value={'test': True})
    )
    monkeypatch.setattr(webhooks, 'get_all_webhook_events', lambda: {event_type.action_type: event_type})
    with scope(event=event, organizer=organizer):
        log = LogEntry.objects.create(event=event, content_object=event, action_type=event_type.action_type)
        webhook = organizer.webhooks.create(enabled=True, target_url='https://example.com/hook', all_events=True)
        webhook.listeners.create(action_type=event_type.action_type)
    enqueue = Mock()
    monkeypatch.setattr(webhooks.send_webhook, 'apply_async', enqueue)
    post = Mock(return_value=SimpleNamespace(status_code=200, text='ok'))
    monkeypatch.setattr(webhooks.requests, 'post', post)

    webhooks.notify_webhooks([log.pk])
    enqueue.assert_not_called()
    allowed = True
    webhooks.notify_webhooks([log.pk])
    enqueue.assert_called_once_with(args=(log.pk, event_type.action_type, webhook.pk))
    # A downgrade must also stop an already queued delivery or retry.
    allowed = False
    webhooks.send_webhook.run(log.pk, event_type.action_type, webhook.pk)
    post.assert_not_called()
    allowed = True
    webhooks.send_webhook.run(log.pk, event_type.action_type, webhook.pk)
    post.assert_called_once()
