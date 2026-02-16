import pytest
from django.test import RequestFactory
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Team, User
from eventyay.control.views.dashboards import widgets_for_event_qs
from eventyay.multidomain.middlewares import SessionMiddleware


@pytest.mark.django_db
def test_tickets_dashboard_link_visible_for_ticket_team(client):
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy')
        user = User.objects.create_user('dummy@dummy.test', 'dummy')
        team = Team.objects.create(organizer=organizer, can_view_orders=True)
        team.members.add(user)
        team.limit_events.add(event)
    client.force_login(user)
    url = reverse('eventyay_common:event.index', kwargs={'organizer': organizer.slug, 'event': event.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert reverse('control:event.index', kwargs={'organizer': organizer.slug, 'event': event.slug}) in response.text


@pytest.mark.django_db
def test_tickets_dashboard_link_disabled_for_talk_only_team(client):
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy')
        user = User.objects.create_user('dummy@dummy.test', 'dummy')
        team = Team.objects.create(organizer=organizer)
        team.members.add(user)
        team.limit_events.add(event)
    client.force_login(user)
    url = reverse('eventyay_common:event.index', kwargs={'organizer': organizer.slug, 'event': event.slug})
    response = client.get(url)
    assert response.status_code == 200
    tickets_url = reverse('control:event.index', kwargs={'organizer': organizer.slug, 'event': event.slug})
    assert tickets_url not in response.text
    assert 'tickets-permission-modal' in response.text
    assert (
        'You require additional permissions to access the tickets dashboard. Please contact the main event organisers.'
        in response.text
    )
    assert 'data-toggle="modal"' in response.text
    assert 'data-target="#tickets-permission-modal"' in response.text


@pytest.mark.django_db
def test_general_dashboard_event_link_for_ticket_team(client):
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy-ticket')
        event = Event.objects.create(organizer=organizer, name='Dummy Event', slug='dummy-ticket')
        user = User.objects.create_user('user-with-orders@example.com', 'test')
        team = Team.objects.create(organizer=organizer, can_view_orders=True)
        team.members.add(user)
        team.limit_events.add(event)
    factory = RequestFactory()
    request = factory.get('/')
    SessionMiddleware(NotImplementedError).process_request(request)
    request.session.save()
    request.user = user
    request.timezone = event.settings.timezone
    with scopes_disabled():
        widgets = list(widgets_for_event_qs(request, Event.objects.filter(pk=event.pk), user, 1))
    assert len(widgets) == 1
    event_widget = widgets[0]
    expected_url = reverse('control:event.index', kwargs={'organizer': organizer.slug, 'event': event.slug})
    assert expected_url in event_widget['content']


@pytest.mark.django_db
def test_general_dashboard_event_link_for_talk_only_user(client):
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy-talk')
        event = Event.objects.create(organizer=organizer, name='Dummy Event', slug='dummy-talk')
        user = User.objects.create_user('talk-only-user@example.com', 'test')
        team = Team.objects.create(organizer=organizer)
        team.members.add(user)
        team.limit_events.add(event)
    factory = RequestFactory()
    request = factory.get('/')
    SessionMiddleware(NotImplementedError).process_request(request)
    request.session.save()
    request.user = user
    request.timezone = event.settings.timezone
    with scopes_disabled():
        widgets = list(widgets_for_event_qs(request, Event.objects.filter(pk=event.pk), user, 1))
    assert len(widgets) == 1
    event_widget = widgets[0]
    expected_url = reverse('eventyay_common:event.index', kwargs={'organizer': organizer.slug, 'event': event.slug})
    assert expected_url in event_widget['content']
