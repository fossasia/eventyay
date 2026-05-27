import pytest
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import Team
from eventyay.base.timeline import TimelineEvent
from eventyay.eventyay_common.permissions import (
    filter_timeline_entry_for_ticket_access,
    user_has_ticket_dashboard_access,
)
from eventyay.eventyay_common.views.dashboards import (
    EVENT_SETTINGS_PERMISSION_DIALOG_ID,
    TICKET_PERMISSION_DIALOG_ID,
    EventWidgetGenerator,
)


@pytest.fixture
def talk_only_team(db, organizer, event, user):
    team = Team.objects.create(
        organizer=organizer,
        name='Talk only',
        all_events=False,
        can_change_submissions=True,
    )
    team.limit_events.add(event)
    team.members.add(user)
    return team


@pytest.fixture
def talk_only_client(client, user, talk_only_team):
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_user_has_ticket_dashboard_access_for_ticket_team(user, organizer, event, team):
    assert user_has_ticket_dashboard_access(user, organizer, event) is True


@pytest.mark.django_db
def test_user_has_ticket_dashboard_access_denied_for_talk_only(user, organizer, event, talk_only_team):
    assert user_has_ticket_dashboard_access(user, organizer, event) is False


@pytest.mark.django_db
def test_generate_ticket_button_shows_permission_dialog_for_talk_only(
    user, organizer, event, talk_only_team, rf
):
    request = rf.get('/')
    request.user = user
    html = EventWidgetGenerator.generate_ticket_button(event, request)
    assert f'data-dialog-target="#{TICKET_PERMISSION_DIALOG_ID}"' in html
    assert f'aria-controls="{TICKET_PERMISSION_DIALOG_ID}"' in html
    assert reverse(
        'control:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    ) not in html


@pytest.mark.django_db
def test_generate_ticket_button_links_to_control_for_ticket_team(user, organizer, event, team, rf):
    request = rf.get('/')
    request.user = user
    html = EventWidgetGenerator.generate_ticket_button(event, request)
    control_url = reverse(
        'control:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    assert control_url in html
    assert TICKET_PERMISSION_DIALOG_ID not in html


@pytest.mark.django_db
def test_filter_timeline_entry_strips_control_edit_urls(event):
    entry = TimelineEvent(
        event=event,
        subevent=None,
        datetime=now(),
        description='Ticket sales',
        edit_url='/control/event/dummy/dummy/settings/tickets',
    )
    filtered = filter_timeline_entry_for_ticket_access(entry, has_ticket_access=False)
    assert filtered.edit_url is None


@pytest.mark.django_db
def test_filter_timeline_entry_keeps_common_edit_urls(event):
    entry = TimelineEvent(
        event=event,
        subevent=None,
        datetime=now(),
        description='Event starts',
        edit_url='/common/organizer/dummy/event/dummy/settings',
    )
    filtered = filter_timeline_entry_for_ticket_access(entry, has_ticket_access=False)
    assert filtered.edit_url == entry.edit_url


@pytest.mark.django_db
def test_event_dashboard_hides_ticket_nav_for_talk_only(talk_only_client, organizer, event):
    url = reverse(
        'eventyay_common:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    response = talk_only_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert reverse(
        'control:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    ) not in content
    assert 'shopstate' in content
    assert 'event-settings-permission-dialog' in content
    assert 'Tickets Dashboard' not in content


@pytest.mark.django_db
def test_event_index_widgets_json_includes_live_status_for_talk_only(talk_only_client, organizer, event):
    url = reverse(
        'eventyay_common:event.index.widgets',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    response = talk_only_client.get(url)
    assert response.status_code == 200
    widgets = response.json()['widgets']
    assert any(
        'shopstate' in widget.get('content', '')
        and widget.get('permission_dialog_id') == EVENT_SETTINGS_PERMISSION_DIALOG_ID
        for widget in widgets
    )


@pytest.mark.django_db
def test_event_dashboard_shows_ticket_links_for_ticket_team(organizer_client, organizer, event):
    url = reverse(
        'eventyay_common:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    response = organizer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert reverse(
        'control:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    ) in content
