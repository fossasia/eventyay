from types import SimpleNamespace

import pytest
from django_scopes import scope

from eventyay.agenda.views.widget import color_etag, event_css


class DummySettings:
    def __init__(self, values):
        self.values = values
        self.lookups = {}

    def get(self, key):
        self.lookups[key] = self.lookups.get(key, 0) + 1
        return self.values.get(key)


def make_event(
    primary_color='#00ff00',
    header_background_color='',
    header_text_color='',
    navigation_text_color='',
):
    return SimpleNamespace(
        visible_primary_color=primary_color,
        settings=DummySettings(
            {
                'header_background_color': header_background_color,
                'header_text_color': header_text_color,
                'navigation_text_color': navigation_text_color,
            }
        ),
    )


@pytest.mark.parametrize('url', ('widgets/schedule.js', 'schedule/widgets/schedule.json'))
@pytest.mark.parametrize(
    'show_schedule,show_widget_if_not_public,expected',
    (
        (True, False, 200),
        (True, True, 200),
        (False, False, 404),
        (False, True, 200),
    ),
)
@pytest.mark.django_db
@pytest.mark.usefixtures('slot', 'other_slot')
def test_widget_pages(
    event,
    client,
    url,
    show_schedule,
    show_widget_if_not_public,
    expected,
):
    event.feature_flags['show_schedule'] = show_schedule
    event.feature_flags['show_widget_if_not_public'] = show_widget_if_not_public
    event.save()
    response = client.get(event.urls.base + url, follow=True)
    assert response.status_code == expected


@pytest.mark.django_db
@pytest.mark.usefixtures('slot', 'other_slot')
def test_widget_data(
    client,
    event,
    django_assert_num_queries,
):
    event.feature_flags['show_schedule'] = True
    event.save()
    with django_assert_num_queries(14):
        response = client.get(event.urls.schedule + 'widgets/schedule.json', follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures('slot', 'other_slot')
def test_widget_data_enriched(client, event):
    event.feature_flags['show_schedule'] = True
    event.save()

    response = client.get(event.urls.schedule + 'widgets/schedule.json?enrich=1', follow=True)

    assert response.status_code == 200
    payload = response.json()
    assert payload['talks']
    assert 'exporters' in payload['talks'][0]
    assert 'exporters' in payload['speakers'][0]


@pytest.mark.django_db
@pytest.mark.usefixtures('slot')
def test_versioned_widget_data(client, event, schedule):
    with scope(event=event):
        event.wip_schedule.freeze('new')

    response = client.get(event.urls.schedule + f'widgets/schedule.json?v={schedule.version}')
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures('slot')
def test_bogus_versioned_widget_data(client, event):
    response = client.get(event.urls.schedule + 'widgets/schedule.json?v=nopedinope')
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures('slot')
def test_anon_cannot_access_wip_schedule(client, event):
    response = client.get(event.urls.schedule + 'widgets/schedule.json?v=wip')
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.usefixtures('slot')
def test_orga_can_access_wip_schedule(orga_client, event):
    response = orga_client.get(event.urls.schedule + 'widgets/schedule.json?v=wip')
    assert response.status_code == 200


def test_event_css_exposes_separate_header_and_navigation_colors(rf):
    request = rf.get('/settings.css')
    request.event = make_event(
        header_background_color='#ffee00',
        header_text_color='#111111',
        navigation_text_color='#222222',
    )

    response = event_css(request)

    assert response.status_code == 200
    assert '--color-primary: #00ff00;' in response.text
    assert '--color-header-background: #ffee00;' in response.text
    assert '--color-header-text: #111111;' in response.text
    assert '--color-header-navigation: #222222;' in response.text


def test_event_css_reads_each_header_setting_once(rf):
    request = rf.get('/settings.css')
    request.event = make_event(
        header_background_color='#ffee00',
        header_text_color='#111111',
        navigation_text_color='#222222',
    )

    response = event_css(request)

    assert response.status_code == 200
    assert request.event.settings.lookups == {
        'header_background_color': 1,
        'header_text_color': 1,
        'navigation_text_color': 1,
    }


def test_event_css_etag_changes_when_header_colors_change(rf):
    request = rf.get('/settings.css')
    request.event = make_event()

    default_etag = color_etag(request)
    request.event = make_event(header_background_color='#ffee00')

    assert color_etag(request) != default_etag


def test_event_css_etag_returns_none_when_no_colors_are_set(rf):
    request = rf.get('/settings.css')
    request.event = make_event(primary_color='')

    assert color_etag(request) == 'none'
