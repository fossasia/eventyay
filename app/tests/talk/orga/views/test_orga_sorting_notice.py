"""Tests for the notice shown above the Rooms, Tracks and Session types tables while they are sorted.

The alert is a flex container, so its sentence and the "Reset to default order" link
must be in one child element. As separate flex items, the space between them is lost
and on phones the link is pushed into a narrow column of its own.
"""

import bs4
import pytest
from django.urls import reverse


LIST_URLS = {
    'rooms': lambda event: reverse(
        'orga:schedule.rooms.list',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    ),
    'tracks': lambda event: event.cfp.urls.tracks,
    'session-types': lambda event: event.cfp.urls.types,
}


@pytest.mark.django_db
@pytest.mark.parametrize('page', LIST_URLS)
def test_sorting_notice_keeps_text_and_link_together(orga_client, event, page):
    response = orga_client.get(f'{LIST_URLS[page](event)}?sort=name')
    assert response.status_code == 200

    # Found by structure, not by its text, so the test also holds when the notice is translated.
    doc = bs4.BeautifulSoup(response.content, 'html.parser')
    (link,) = doc.select('.alert a.alert-link')
    alert = link.find_parent(class_='alert')

    (content,) = alert.find_all(recursive=False)
    assert link in content.descendants
    assert content.get_text(strip=True) != link.get_text(strip=True)
    assert not ''.join(alert.find_all(string=True, recursive=False)).strip()
