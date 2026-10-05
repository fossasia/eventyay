import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event


@pytest.fixture
def multiple_events(organizer):
    with scope(organizer=organizer):
        e1 = Event.objects.create(
            organizer=organizer,
            name='Alpha Summit',
            slug='alpha-summit',
            date_from=now(),
            is_public=True,
            plugins='eventyay.plugins.checkinlists',
        )
        e2 = Event.objects.create(
            organizer=organizer,
            name='Beta Conference',
            slug='beta-conf',
            date_from=now(),
            is_public=True,
            plugins='eventyay.plugins.checkinlists',
        )
        e3 = Event.objects.create(
            organizer=organizer,
            name='Gamma Workshop',
            slug='gamma-work',
            date_from=now(),
            is_public=True,
            plugins='eventyay.plugins.checkinlists',
        )
    return [e1, e2, e3]


@pytest.mark.django_db
def test_events_list_sorting_links_present(organizer_client, multiple_events):
    url = reverse('eventyay_common:events')
    response = organizer_client.get(url)
    assert response.status_code == 200

    content = response.content.decode()
    # Check sorting controls for Event name
    assert 'ordering=-name' in content
    assert 'ordering=name' in content

    # Check sorting controls for Short form
    assert 'ordering=-slug' in content
    assert 'ordering=slug' in content


@pytest.mark.django_db
def test_events_list_sorting_by_name(organizer_client, multiple_events):
    url = reverse('eventyay_common:events')

    # Ascending name ordering
    response_asc = organizer_client.get(url, {'ordering': 'name'})
    assert response_asc.status_code == 200
    events_asc = list(response_asc.context['events'])
    names_asc = [str(e.name) for e in events_asc]
    assert names_asc == ['Alpha Summit', 'Beta Conference', 'Gamma Workshop']

    # Descending name ordering
    response_desc = organizer_client.get(url, {'ordering': '-name'})
    assert response_desc.status_code == 200
    events_desc = list(response_desc.context['events'])
    names_desc = [str(e.name) for e in events_desc]
    assert names_desc == ['Gamma Workshop', 'Beta Conference', 'Alpha Summit']


@pytest.mark.django_db
def test_events_list_sorting_by_slug(organizer_client, multiple_events):
    url = reverse('eventyay_common:events')

    # Ascending slug ordering
    response_asc = organizer_client.get(url, {'ordering': 'slug'})
    assert response_asc.status_code == 200
    events_asc = list(response_asc.context['events'])
    slugs_asc = [e.slug for e in events_asc]
    assert slugs_asc == ['alpha-summit', 'beta-conf', 'gamma-work']

    # Descending slug ordering
    response_desc = organizer_client.get(url, {'ordering': '-slug'})
    assert response_desc.status_code == 200
    events_desc = list(response_desc.context['events'])
    slugs_desc = [e.slug for e in events_desc]
    assert slugs_desc == ['gamma-work', 'beta-conf', 'alpha-summit']
