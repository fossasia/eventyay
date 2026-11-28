import time
from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import EventAnonymizationRun, Order, Team, User
from eventyay.base.services.organizer_creation import create_core_team
from eventyay.base.settings import GlobalSettingsObject


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def site_url(settings):
    settings.SITE_URL = 'https://testserver'


@pytest.fixture
def owner(organizer):
    user = User.objects.create_user('owner@example.com', 'owner')
    create_core_team(organizer, user)
    return user


@pytest.fixture
def helper(organizer):
    user = User.objects.create_user('helper@example.com', 'helper')
    team = Team.objects.create(organizer=organizer, name='Helpers', all_events=True, can_change_event_settings=True)
    team.members.add(user)
    return user


@pytest.fixture
def ended_event(event):
    event.date_from = event.date_to = now() - timedelta(days=30)
    event.live = False
    event.save()
    return event


def open_session(client, user):
    client.force_login(user)
    session = client.session
    session['eventyay_auth_login_time'] = int(time.time())
    session.save()


def runs(event):
    with scopes_disabled():
        return list(EventAnonymizationRun.objects.filter(event=event))


def url(event, name='anonymize'):
    return f'/control/event/{event.organizer.slug}/{event.slug}/{name}/'


def valid_post(event, **overrides):
    return {'invoices_downloaded': 'on', 'name': str(event.name), **overrides}


def make_order(event, code='AAAAA'):
    with scope(event=event, organizer=event.organizer):
        return Order.objects.create(event=event, code=code, email='buyer@example.org', total=0, expires=now())


def test_non_core_team_member_cannot_open_or_post(client, helper, ended_event):
    open_session(client, helper)
    assert client.get(url(ended_event)).status_code == 403
    assert client.post(url(ended_event), valid_post(ended_event)).status_code == 403
    assert not runs(ended_event)


def test_core_team_member_sees_the_summary(client, owner, ended_event):
    make_order(ended_event)
    open_session(client, owner)
    response = client.get(url(ended_event))
    content = response.content.decode()
    assert response.status_code == 200
    assert '1 order' in content and 'Tax law' in content and 'invoices' in content


def test_blocked_before_the_minimum_days(client, owner, event):
    event.date_from = event.date_to = now() - timedelta(days=3)
    event.save()
    open_session(client, owner)
    assert 'can be anonymized from' in client.get(url(event)).content.decode()
    client.post(url(event), valid_post(event))
    assert not runs(event)


def test_minimum_days_follow_the_admin_setting(client, owner, event):
    event.date_from = event.date_to = now() - timedelta(days=3)
    event.save()
    GlobalSettingsObject().settings.set('ticketing_retention_manual_min_days', 2)
    open_session(client, owner)
    assert 'can be anonymized from' not in client.get(url(event)).content.decode()


@pytest.mark.parametrize('overrides', [{'name': 'Wrong name'}, {'invoices_downloaded': ''}])
def test_wrong_name_or_missing_invoice_confirmation_is_rejected(client, owner, ended_event, overrides, mocker):
    start = mocker.patch('eventyay.control.views.event.anonymize_event.apply_async')
    open_session(client, owner)
    response = client.post(url(ended_event), valid_post(ended_event, **overrides))
    assert response.status_code == 200
    start.assert_not_called()
    assert not runs(ended_event)


def test_valid_request_starts_the_run_after_commit(
    client, owner, ended_event, mocker, django_capture_on_commit_callbacks
):
    start = mocker.patch('eventyay.control.views.event.anonymize_event.apply_async')
    open_session(client, owner)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url(ended_event), valid_post(ended_event))
        start.assert_not_called()
    assert response.status_code == 302
    start.assert_called_once_with(args=(ended_event.pk, 'manual', owner.pk))
    [run] = runs(ended_event)
    assert run.status == run.Status.RUNNING and run.requested_by == owner
    assert ended_event.logentry_set.filter(
        action_type='eventyay.event.ticketing_data.anonymization.requested', user=owner
    ).exists()
    assert 'Anonymization is running' in client.get(url(ended_event)).content.decode()


def test_second_request_is_refused_while_running_or_done(client, owner, ended_event, mocker):
    start = mocker.patch('eventyay.control.views.event.anonymize_event.apply_async')
    with scope(event=ended_event, organizer=ended_event.organizer):
        EventAnonymizationRun.objects.create(event=ended_event, trigger='manual')
    open_session(client, owner)
    client.post(url(ended_event), valid_post(ended_event))
    start.assert_not_called()


def test_failed_run_can_be_resumed(client, owner, ended_event, mocker, django_capture_on_commit_callbacks):
    start = mocker.patch('eventyay.control.views.event.anonymize_event.apply_async')
    with scope(event=ended_event, organizer=ended_event.organizer):
        EventAnonymizationRun.objects.create(
            event=ended_event, trigger='manual', status='failed', error='OperationalError', finished=now()
        )
    open_session(client, owner)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url(ended_event), valid_post(ended_event))
    start.assert_called_once()
    [run] = runs(ended_event)
    assert run.status == run.Status.RUNNING and not run.error and run.finished is None


def test_end_to_end_anonymizes_orders(client, owner, ended_event, django_capture_on_commit_callbacks):
    order = make_order(ended_event)
    open_session(client, owner)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url(ended_event), valid_post(ended_event))
    with scope(event=ended_event, organizer=ended_event.organizer):
        order.refresh_from_db()
        assert order.is_anonymized and order.email.endswith('@eventyay.invalid')
        assert EventAnonymizationRun.objects.get(event=ended_event).status == 'completed'
    assert 'was anonymized on' in client.get(url(ended_event)).content.decode()


def test_danger_zone_card_is_only_shown_to_the_core_team(client, owner, helper, ended_event):
    page = f'/common/event/{ended_event.organizer.slug}/{ended_event.slug}/settings/'
    open_session(client, owner)
    assert url(ended_event) in client.get(page).content.decode()
    open_session(client, helper)
    assert url(ended_event) not in client.get(page).content.decode()


def test_old_login_must_reauthenticate(client, owner, ended_event):
    client.force_login(owner)
    session = client.session
    session['eventyay_auth_login_time'] = int(time.time()) - 7200
    session.save()
    response = client.get(url(ended_event))
    assert response.status_code == 302 and '/reauth/' in response['Location']
