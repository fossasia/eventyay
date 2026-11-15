import pytest
from django.contrib.contenttypes.models import ContentType
from django_scopes import scopes_disabled

from eventyay.base.models import Event, LogEntry, Team


@pytest.fixture
def orga_client(client, user, event, settings):
    """Client of a team member with access to the event's Talk dashboard."""
    settings.SITE_URL = 'https://testserver'
    settings.SITE_NETLOC = 'testserver'
    with scopes_disabled():
        team = Team.objects.create(
            organizer=event.organizer,
            name='Talk organisers',
            can_change_event_settings=True,
            can_change_submissions=True,
        )
        team.limit_events.add(event)
        team.members.add(user)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_talk_dashboard_survives_log_entry_of_uninstalled_model(orga_client, event):
    """A log entry whose model is gone (e.g. from a removed plugin) must not break the dashboard."""
    gone = ContentType.objects.create(app_label='removedplugin', model='proposal')
    with scopes_disabled():
        orphan = LogEntry.objects.create(
            event=event, content_type=gone, object_id=1, action_type='eventyay.submission.update'
        )
        known = LogEntry.objects.create(
            event=event,
            content_type=ContentType.objects.get_for_model(Event),
            object_id=event.pk,
            action_type='eventyay.cfp.update',
        )

    response = orga_client.get(f'/orga/event/{event.organizer.slug}/{event.slug}/')

    assert response.status_code == 200
    activity = {log.pk: log for log in response.context['recent_talk_activity']}
    assert activity[orphan.pk].content_object is None
    assert activity[known.pk].content_object == event
