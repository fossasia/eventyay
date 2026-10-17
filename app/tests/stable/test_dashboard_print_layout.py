import pytest
from django.test import override_settings


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('path', ['/control/event/{organizer}/{event}/', '/common/event/{organizer}/{event}/'])
def test_event_dashboards_leave_the_navigation_out_of_the_printout(organizer_client, organizer, event, path):
    """The sidebar and the Home/Tickets/Talks buttons are hidden when printing."""
    response = organizer_client.get(path.format(organizer=organizer.slug, event=event.slug))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'class="navigation-button hidden-print"' in html
    assert 'class="navbar-default sidebar hidden-print"' in html


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_talk_pages_leave_the_sidebar_out_of_the_printout(organizer_client):
    response = organizer_client.get('/orga/event/')

    assert response.status_code == 200
    assert 'class="nav flex-column sidebar d-print-none"' in response.content.decode()
