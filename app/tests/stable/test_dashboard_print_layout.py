import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.test import override_settings
from django.urls import reverse


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
    assert 'class="nojs sidebar-minimized dashboard-print"' in html


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_organizer_dashboard_uses_the_dashboard_print_layout(organizer_client, organizer):
    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    response = organizer_client.get(url)

    assert response.status_code == 200
    assert 'class="nojs sidebar-minimized dashboard-print"' in response.content.decode()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_other_pages_keep_their_print_layout(organizer_client):
    """Only the dashboards opt in to the dashboard print rules."""
    response = organizer_client.get(reverse('eventyay_common:events'))

    assert response.status_code == 200
    assert 'dashboard-print' not in response.content.decode()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_talk_pages_leave_the_sidebar_out_of_the_printout(organizer_client):
    response = organizer_client.get('/orga/event/')

    assert response.status_code == 200
    assert 'class="nav flex-column sidebar d-print-none"' in response.content.decode()


def test_navbar_is_left_out_of_the_printout():
    """The navbar is fixed, so a printout would repeat it on every page, over the content."""
    css = Path(finders.find('common/css/_navbar.css')).read_text()

    print_rules = re.search(r'@media print\s*\{(.*?)\n\}', css, flags=re.S)
    assert print_rules
    assert re.search(r'nav\.navbar\.navbar-inverse\s*\{\s*display:\s*none;', print_rules.group(1))
