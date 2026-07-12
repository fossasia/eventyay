import pytest
from unittest.mock import MagicMock
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from django.urls import clear_url_caches, get_script_prefix, reverse, set_script_prefix
from django.utils.timezone import now

from eventyay.base.models import Team
from eventyay.base.timeline import TimelineEvent
from eventyay.eventyay_common.permissions import (
    filter_timeline_entry_for_ticket_access,
    get_cached_event_dashboard_access,
    user_has_talk_dashboard_access,
    user_has_ticket_dashboard_access,
    user_has_video_dashboard_access,
)
from eventyay.eventyay_common.views.dashboards import (
    EVENT_SETTINGS_PERMISSION_DIALOG_ID,
    TICKET_PERMISSION_DIALOG_ID,
    TALK_PERMISSION_DIALOG_ID,
    VIDEO_PERMISSION_DIALOG_ID,
    EventWidgetGenerator,
    filter_common_event_dashboard_widgets,
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
def video_only_team(db, organizer, event, user):
    team = Team.objects.create(
        organizer=organizer,
        name='Video only',
        all_events=False,
        can_video_create_stages=True,
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
def test_user_has_dashboard_access_denied_for_anonymous_user(organizer, event):
    anonymous = AnonymousUser()
    assert user_has_ticket_dashboard_access(anonymous, organizer, event) is False
    assert user_has_talk_dashboard_access(anonymous, organizer, event) is False
    assert user_has_video_dashboard_access(anonymous, organizer, event) is False


@pytest.mark.django_db
def test_get_cached_event_dashboard_access_for_anonymous_user(rf, organizer, event):
    request = rf.get('/')
    request.user = AnonymousUser()
    access = get_cached_event_dashboard_access(request, request.user, organizer, event)
    assert access['has_ticket_access'] is False
    assert access['has_talk_access'] is False
    assert access['has_video_access'] is False
    assert access['can_view_orders'] is False
    assert access['can_change_event_settings'] is False


@pytest.mark.django_db
def test_filter_common_event_dashboard_widgets_uses_ticket_dashboard_access():
    widgets = [
        {'key': 'shop_state', 'content': 'live'},
        {'content': '<div class="numwidget">orders</div>'},
    ]
    filtered = filter_common_event_dashboard_widgets(
        widgets,
        has_ticket_dashboard_access=True,
        can_change_event_settings=False,
    )
    assert len(filtered) == 2

    filtered_talk_only = filter_common_event_dashboard_widgets(
        widgets,
        has_ticket_dashboard_access=False,
        can_change_event_settings=False,
    )
    assert len(filtered_talk_only) == 1
    assert filtered_talk_only[0]['key'] == 'shop_state'


@pytest.mark.django_db
def test_generate_ticket_button_shows_permission_dialog_for_talk_only(
    user, organizer, event, talk_only_team, rf
):
    request = rf.get('/')
    request.user = user
    request.session = MagicMock()
    html = EventWidgetGenerator.generate_ticket_button(event, request)
    assert '<button type="button"' in html
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
    request.session = MagicMock()
    html = EventWidgetGenerator.generate_ticket_button(event, request)
    control_url = reverse(
        'control:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    assert control_url in html
    assert TICKET_PERMISSION_DIALOG_ID not in html


@pytest.mark.django_db
def test_generate_video_button_links_for_video_only_team(user, organizer, event, video_only_team, rf):
    request = rf.get('/')
    request.user = user
    request.session = MagicMock()
    html = EventWidgetGenerator.generate_video_button(event, request)
    video_url = reverse(
        'eventyay_common:event.create_access_to_video',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    assert video_url in html
    assert VIDEO_PERMISSION_DIALOG_ID not in html


@pytest.mark.django_db
def test_generate_video_button_shows_video_permission_dialog_for_talk_only(
    user, organizer, event, talk_only_team, rf
):
    request = rf.get('/')
    request.user = user
    request.session = MagicMock()
    html = EventWidgetGenerator.generate_video_button(event, request)
    assert '<button type="button"' in html
    assert f'data-dialog-target="#{VIDEO_PERMISSION_DIALOG_ID}"' in html
    assert f'aria-controls="{VIDEO_PERMISSION_DIALOG_ID}"' in html
    assert TICKET_PERMISSION_DIALOG_ID not in html
    assert reverse(
        'eventyay_common:event.create_access_to_video',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    ) not in html


@pytest.mark.django_db
def test_filter_timeline_entry_strips_control_edit_urls_with_base_path(event):
    old_prefix = get_script_prefix()
    try:
        set_script_prefix('/tickets/')
        clear_url_caches()
        with override_settings(FORCE_SCRIPT_NAME='/tickets', BASE_PATH='/tickets'):
            edit_url = reverse(
                'control:event.settings.tickets',
                kwargs={'organizer': event.organizer.slug, 'event': event.slug},
            )
            entry = TimelineEvent(
                event=event,
                subevent=None,
                datetime=now(),
                description='Ticket sales',
                edit_url=edit_url,
            )
            filtered = filter_timeline_entry_for_ticket_access(entry, has_ticket_access=False)
            assert filtered.edit_url is None
            assert edit_url.startswith('/tickets/control/')
    finally:
        set_script_prefix(old_prefix)
        clear_url_caches()


@pytest.mark.django_db
def test_filter_timeline_entry_strips_control_edit_urls(event):
    entry = TimelineEvent(
        event=event,
        subevent=None,
        datetime=now(),
        description='Ticket sales',
        edit_url=reverse(
            'control:event.settings.tickets',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        ),
    )
    filtered = filter_timeline_entry_for_ticket_access(entry, has_ticket_access=False)
    assert filtered.edit_url is None


@pytest.mark.django_db
def test_filter_timeline_entry_strips_control_urls_with_query_string(event):
    entry = TimelineEvent(
        event=event,
        subevent=None,
        datetime=now(),
        description='Ticket sales',
        edit_url=(
            reverse(
                'control:event.settings.tickets',
                kwargs={'organizer': event.organizer.slug, 'event': event.slug},
            )
            + '?next=/common/'
        ),
    )
    filtered = filter_timeline_entry_for_ticket_access(entry, has_ticket_access=False)
    assert filtered.edit_url is None


@pytest.mark.django_db
def test_filter_timeline_entry_keeps_urls_with_control_only_in_query(event):
    entry = TimelineEvent(
        event=event,
        subevent=None,
        datetime=now(),
        description='Event starts',
        edit_url=f'/common/organizer/{event.organizer.slug}/event/{event.slug}/settings?next=/control/',
    )
    filtered = filter_timeline_entry_for_ticket_access(entry, has_ticket_access=False)
    assert filtered.edit_url == entry.edit_url


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
def test_common_dashboard_includes_ticket_permission_dialog_for_talk_only(
    talk_only_client, organizer, event
):
    url = reverse('eventyay_common:dashboard')
    response = talk_only_client.get(url)
    assert response.status_code == 200
    assert 'ticket-permission-dialog' in response.content.decode()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
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
    assert 'class="shopstate"' in content
    assert 'event-settings-permission-dialog' in content
    assert 'Click here to change' not in content
    assert 'Tickets Dashboard' not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
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
@override_settings(SITE_URL='https://testserver')
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


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_event_dashboard_hides_talk_nav_for_ticket_only(organizer_client, organizer, event):
    url = reverse(
        'eventyay_common:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    response = organizer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Organizer client is a ticket-only team member, so they shouldn't see talks navigation/dashboard
    assert reverse(
        'orga:event.dashboard',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    ) not in content
    assert 'Talks Dashboard' not in content


@pytest.mark.django_db
def test_generate_talk_button_shows_permission_dialog_for_ticket_only(user, organizer, event, team, rf):
    request = rf.get('/')
    request.user = user
    request.session = MagicMock()
    # team fixture gives user ticket access but no talk access
    html = EventWidgetGenerator.generate_talk_button(event, request)
    assert '<a href="#" class="middle-component"' in html
    assert 'role="button"' in html
    assert f'data-dialog-target="#{TALK_PERMISSION_DIALOG_ID}"' in html
    assert f'aria-controls="{TALK_PERMISSION_DIALOG_ID}"' in html
    assert reverse(
        'orga:event.dashboard',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    ) not in html


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_control_event_dashboard_hides_talk_and_video_links_for_ticket_only(organizer_client, organizer, event):
    url = reverse(
        'control:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    response = organizer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Ticket-only user should not see Talks or Videos buttons on the tickets dashboard page
    assert reverse(
        'orga:event.dashboard',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    ) not in content
    assert reverse(
        'eventyay_common:event.create_access_to_video',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    ) not in content

