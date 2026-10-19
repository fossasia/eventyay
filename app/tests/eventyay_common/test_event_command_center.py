"""Tests for Unified Event Command Center (Issue #5092)."""
from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Order, RequiredAction, Submission, SubmissionStates, Team, User


@pytest.fixture
def command_center_url(event):
    return reverse(
        'eventyay_common:event.index',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_renders_sections(organizer_client, event, organizer, command_center_url):
    """Verify that the command center renders all key sections."""
    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    content = response.content.decode()

    # Layout container
    assert 'cc-dashboard' in content

    # 1. Header & Quick Info
    assert 'cc-header-top' in content
    assert 'cc-copy-btn' in content
    assert event.name in content

    # 2. Lifecycle Timeline
    assert 'dashboard-timeline' in content
    assert 'timeline-step' in content

    # 3. Action Required
    assert 'cc-action-title' in content

    # 4. At-a-glance KPIs
    assert 'cc-kpi-grid' in content
    assert 'cc-kpi-card' in content

    # 5. Component Dashboards
    assert 'cc-component-grid' in content
    assert 'cc-component-card' in content

    # 6 & 7. Milestones and Teams
    assert 'cc-milestones-card' in content
    assert 'cc-teams-card' in content

    # 8. Analytics Overview
    assert 'cc-analytics-grid' in content

    # 9. Recent Activity
    assert 'cc-activity-feed' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_context_data(organizer_client, event, command_center_url):
    """Verify that the view provides all required context dictionaries and lists."""
    response = organizer_client.get(command_center_url)
    assert response.status_code == 200

    assert 'header_data' in response.context
    assert response.context['header_data']['public_url'] is not None

    assert 'workflow_timeline' in response.context
    assert len(response.context['workflow_timeline']) == 6

    assert 'action_required' in response.context
    assert isinstance(response.context['action_required'], list)

    assert 'at_a_glance' in response.context
    assert 'component_cards' in response.context
    assert len(response.context['component_cards']) >= 3

    assert 'upcoming_milestones' in response.context
    assert 'organiser_info' in response.context
    assert 'analytics_overview' in response.context
    assert 'recent_activity' in response.context


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_action_required_cards_and_empty_state(organizer_client, event, command_center_url):
    """When setup tasks remain, cards are shown; when all clear, empty state is displayed."""
    # Initially without products, an action card for product setup is rendered
    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'cc-action-card' in content
    assert 'Setup tasks remaining' in content

    # Once a product exists, the setup action is resolved
    with scopes_disabled():
        event.products.create(name='Standard Ticket', default_price=10)

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'cc-action-empty' in content
    assert 'No action required' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_permission_talk_only(client, user, organizer, event, command_center_url):
    """A talk-only team member sees talk info but no ticket or order data."""
    team = Team.objects.create(
        organizer=organizer,
        name='Talk Only Team',
        all_events=False,
        can_change_submissions=True,
        can_view_orders=False,
        can_change_items=False,
        can_change_event_settings=False,
    )
    team.limit_events.add(event)
    team.members.add(user)

    client.force_login(user)
    response = client.get(command_center_url)
    assert response.status_code == 200

    content = response.content.decode()
    # Tickets control dashboard link should NOT be present
    assert reverse('control:event.index', kwargs={'organizer': organizer.slug, 'event': event.slug}) not in content
    # Manage teams link should NOT be present for user without organizer settings and team permissions
    assert 'Manage teams &amp; roles' not in content and 'Manage teams & roles' not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_team_manage_url_permission_gating(
    organizer_client, client, organizer, event, command_center_url
):
    """Admin sees manage teams link; user without organizer permissions does not."""
    # organizer_client is an organizer admin
    response_admin = organizer_client.get(command_center_url)
    assert response_admin.status_code == 200
    assert response_admin.context['organiser_info']['manage_url'] is not None
    assert 'Manage teams' in response_admin.content.decode()

    # user without organizer permissions
    viewer_user = User.objects.create_user(email='viewer@example.com', password='viewerpass123')
    team = Team.objects.create(
        organizer=organizer,
        name='Viewer Team',
        all_events=False,
        can_view_orders=True,
    )
    team.limit_events.add(event)
    team.members.add(viewer_user)

    client.force_login(viewer_user)
    response_viewer = client.get(command_center_url)
    assert response_viewer.status_code == 200
    assert response_viewer.context['organiser_info']['manage_url'] is None
    viewer_content = response_viewer.content.decode()
    assert 'Manage teams' not in viewer_content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_past_event_status_consistency(organizer_client, event, command_center_url):
    """Past live event shows Past in both header and KPI card."""
    with scopes_disabled():
        event.live = True
        event.date_from = now() - timedelta(days=10)
        event.date_to = now() - timedelta(days=2)
        event.save()

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    assert str(response.context['header_data']['event_status']) == 'Past'
    assert str(response.context['at_a_glance']['event_status_text']) == 'Past'
    assert response.context['header_data']['event_status_class'] == 'past'
    assert response.context['at_a_glance']['event_status_class'] == 'past'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_ticket_shop_testmode_workflow_status(organizer_client, event, command_center_url):
    """When event testmode is active, ticketing step is labeled 'In test mode' rather than 'Live'."""
    with scopes_disabled():
        event.live = True
        event.testmode = True
        event.tickets_published = True
        event.save()

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    workflow = response.context['workflow_timeline']
    ticketing_step = next(s for s in workflow if s['name'] == 'Ticketing')
    assert str(ticketing_step['status_text']) == 'In test mode'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_approval_url_status_pa(organizer_client, event, command_center_url):
    """Pending approvals action card links to ?status=pa."""
    with scopes_disabled():
        Order.objects.create(
            event=event,
            status=Order.STATUS_PENDING,
            require_approval=True,
            total=10,
        )

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    actions = response.context['action_required']
    approval_action = next((a for a in actions if a['id'] == 'orders-approval'), None)
    assert approval_action is not None
    assert '?status=pa' in approval_action['url']


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_confirmed_speakers_count(organizer_client, event, team, command_center_url):
    """Confirmed speakers count includes speakers on confirmed submissions before schedule release."""
    with scopes_disabled():
        team.can_change_submissions = True
        team.save()
        speaker = User.objects.create_user(email='confirmed_speaker@example.com', password='pass')
        st = event.submission_types.create(name='Keynote', default_duration=30)
        sub = Submission.objects.create(
            event=event,
            submission_type=st,
            title='Confirmed Talk',
            state=SubmissionStates.CONFIRMED,
        )
        sub.speakers.add(speaker)

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    assert response.context['at_a_glance']['speakers_confirmed'] == 1
    talks_card = next(c for c in response.context['component_cards'] if c['id'] == 'talks')
    speaker_metric = next(m for m in talks_card['metrics'] if m['label'] == 'Speakers')
    assert speaker_metric['value'] == 1


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_read_only_schedule_no_wip_created(organizer_client, event, command_center_url):
    """Rendering command center does not create draft schedules."""
    with scopes_disabled():
        initial_schedules_count = event.schedules.count()

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200

    with scopes_disabled():
        assert event.schedules.count() == initial_schedules_count


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_milestones_schedule_url(organizer_client, client, organizer, event, team, command_center_url):
    """Admin with talk access sees schedule link in milestones; user without talk access does not."""
    team.can_change_submissions = True
    team.save()

    response_admin = organizer_client.get(command_center_url)
    assert response_admin.status_code == 200
    assert response_admin.context['milestones_schedule_url'] is not None

    ticket_user = User.objects.create_user(email='ticket_user@example.com', password='pass')
    ticket_team = Team.objects.create(
        organizer=organizer,
        name='Ticket Only Team',
        all_events=False,
        can_view_orders=True,
    )
    ticket_team.limit_events.add(event)
    ticket_team.members.add(ticket_user)

    client.force_login(ticket_user)
    response_user = client.get(command_center_url)
    assert response_user.status_code == 200
    assert response_user.context['milestones_schedule_url'] is None


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_recent_activity_logentry(organizer_client, event, command_center_url):
    """LogEntry records render without TypeError in recent activity feed."""
    with scopes_disabled():
        event.log_action('eventyay.event.settings')

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    assert len(response.context['recent_activity']) == 1
    assert response.context['recent_activity'][0]['display'] is not None


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_header_ticket_shop_disabled_fallback(organizer_client, event, command_center_url, monkeypatch):
    """When ticket shop status text is empty, the fallback string 'Disabled' is rendered via template."""
    from eventyay.eventyay_common.views.dashboards import EventIndexView
    orig_header = EventIndexView._get_header_data

    def mock_header(self, e, req):
        data = orig_header(self, e, req)
        data['ticket_shop_status'] = {'class': 'info', 'icon': 'fa-ticket', 'text': ''}
        return data

    monkeypatch.setattr(EventIndexView, '_get_header_data', mock_header)

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Ticket shop:' in content
    assert 'Disabled' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_organizer_all_events_teams(organizer_client, organizer, event, command_center_url):
    """Core organizer teams with all_events=True appear in organiser_info teams."""
    with scopes_disabled():
        Team.objects.create(
            organizer=organizer,
            name='Global Core Team',
            all_events=True,
            can_change_event_settings=True,
        )
    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    team_names = [t['name'] for t in response.context['organiser_info']['teams']]
    assert 'Global Core Team' in team_names


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_shared_submission_metrics_aggregation(organizer_client, event, team, command_center_url):
    """Submission and speaker metrics are computed once via aggregate rather than redundant queries."""
    with scopes_disabled():
        team.can_change_submissions = True
        team.save()
        st = event.submission_types.create(name='Standard', default_duration=30)
        speaker = User.objects.create_user(email='spk_test@example.com', password='pass')
        sub1 = Submission.objects.create(
            event=event, submission_type=st, title='Talk 1', state=SubmissionStates.CONFIRMED
        )
        sub1.speakers.add(speaker)
        Submission.objects.create(event=event, submission_type=st, title='Talk 2', state=SubmissionStates.ACCEPTED)
        Submission.objects.create(event=event, submission_type=st, title='Talk 3', state=SubmissionStates.REJECTED)

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    assert response.context['analytics_overview']['proposal_stats'] == {
        'submitted': 3,
        'accepted': 1,
        'confirmed': 1,
        'rejected': 1,
    }
    assert response.context['at_a_glance']['sessions_confirmed'] == 1
    assert response.context['at_a_glance']['speakers_confirmed'] == 1


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_url_reverse_failure_safe_fallback(organizer_client, event, command_center_url, monkeypatch):
    """If reverse or eventreverse raises NoReverseMatch, view still renders gracefully."""
    from django.urls import NoReverseMatch

    import eventyay.eventyay_common.views.dashboards as dashboards_mod

    def mock_eventreverse(*args, **kwargs):
        raise NoReverseMatch('Mock reverse error')

    monkeypatch.setattr(dashboards_mod, 'eventreverse', mock_eventreverse)

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    assert response.context['header_data']['public_url'] == ''


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_checkin_category_badge(organizer_client, event, command_center_url):
    """Check-in category log entries map to cc-cat-check-in badge class."""
    from django.contrib.contenttypes.models import ContentType

    from eventyay.base.models import CheckinList

    with scopes_disabled():
        cl = CheckinList.objects.create(event=event, name='Default')
        ct = ContentType.objects.get_for_model(CheckinList)
        event.logentry_set.create(content_type=ct, object_id=cl.pk, action_type='eventyay.event.checkin')

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'cc-cat-check-in' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_required_action_merged_and_discardable(organizer_client, event, command_center_url):
    """Active RequiredAction appears in action_required cards and can be dismissed via discard_url."""
    with scopes_disabled():
        req_action = RequiredAction.objects.create(
            event=event,
            action_type='test.operational.alert',
        )

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    actions = response.context['action_required']
    alert_card = next((a for a in actions if a['id'] == f'required-action-{req_action.id}'), None)
    assert alert_card is not None
    assert alert_card['discard_url'] is not None

    content = response.content.decode()
    assert 'Operational alert' in content
    assert alert_card['discard_url'] in content

    # Post to discard URL to resolve the issue
    discard_resp = organizer_client.post(alert_card['discard_url'])
    assert discard_resp.status_code in (302, 200)
    req_action.refresh_from_db()
    assert req_action.done is True



