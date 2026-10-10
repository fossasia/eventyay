import json
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils import translation
from django_scopes import scope

from eventyay.agenda.management.commands.export_schedule_html import event_urls
from eventyay.agenda.views.schedule import schedule_messages
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
    menu_text_scroll_over_color='',
):
    return SimpleNamespace(
        visible_primary_color=primary_color,
        settings=DummySettings(
            {
                'header_background_color': header_background_color,
                'header_text_color': header_text_color,
                'navigation_text_color': navigation_text_color,
                'menu_text_scroll_over_color': menu_text_scroll_over_color,
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
    if expected == 200:
        event.talks_published = True
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
    event.talks_published = True
    event.save()
    with django_assert_num_queries(19):
        response = client.get(event.urls.schedule + 'widgets/schedule.json', follow=True)
    assert response.status_code == 200
    assert 'abstract' in response.json()['talks'][0]


@pytest.mark.django_db
@pytest.mark.usefixtures('slot', 'other_slot')
def test_widget_data_compact_day_omits_abstract(client, event, slot):
    event.feature_flags['show_schedule'] = True
    event.talks_published = True
    event.save()
    with scope(event=event):
        day = slot.local_start.date().isoformat()
        abstract = slot.submission.abstract
    response = client.get(
        event.urls.schedule + f'widgets/schedule.json?compact=1&date={day}',
        follow=True,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['compact'] is True
    assert payload['date'] == day
    talk = next(item for item in payload['talks'] if item.get('code') == slot.submission.code)
    assert 'abstract' not in talk
    assert abstract not in response.content.decode()
    assert 'qrcodes' not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.usefixtures('slot')
def test_widget_data_rejects_invalid_day(client, event):
    event.feature_flags['show_schedule'] = True
    event.talks_published = True
    event.save()
    response = client.get(event.urls.schedule + 'widgets/schedule.json?compact=1&date=nope', follow=True)
    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.usefixtures('slot')
def test_widget_talk_detail_has_text_without_qrcodes(client, event, slot):
    event.feature_flags['show_schedule'] = True
    event.talks_published = True
    event.save()
    response = client.get(
        event.urls.schedule + f'widgets/schedule.json?talk={slot.submission.code}',
        follow=True,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['code'] == slot.submission.code
    assert payload['abstract'] == slot.submission.abstract
    assert 'qrcodes' not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.usefixtures('slot', 'other_slot')
def test_widget_data_enriched(client, event):
    event.feature_flags['show_schedule'] = True
    event.talks_published = True
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
        event.talks_published = True
        event.save(update_fields=['talks_published'])
        event.wip_schedule.freeze('new')

    response = client.get(event.urls.schedule + f'widgets/schedule.json?v={schedule.version}')
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures('slot')
def test_bogus_versioned_widget_data(client, event):
    event.talks_published = True
    event.save(update_fields=['talks_published'])
    response = client.get(event.urls.schedule + 'widgets/schedule.json?v=nopedinope')
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures('slot')
def test_anon_cannot_access_wip_schedule(client, event):
    event.talks_published = True
    event.save(update_fields=['talks_published'])
    response = client.get(event.urls.schedule + 'widgets/schedule.json?v=wip')
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.usefixtures('slot')
def test_orga_can_access_wip_schedule(orga_client, event):
    event.talks_published = True
    event.save(update_fields=['talks_published'])
    response = orga_client.get(event.urls.schedule + 'widgets/schedule.json?v=wip')
    assert response.status_code == 200


def test_event_css_exposes_separate_header_and_navigation_colors(rf):
    request = rf.get('/settings.css')
    request.event = make_event(
        header_background_color='#ffee00',
        header_text_color='#111111',
        navigation_text_color='#222222',
        menu_text_scroll_over_color='#333333',
    )

    response = event_css(request)

    assert response.status_code == 200
    assert '--color-primary: #00ff00;' in response.text
    assert '--color-header-background: #ffee00;' in response.text
    assert '--color-header-text: #111111;' in response.text
    assert '--color-header-navigation: #222222;' in response.text
    assert '--color-header-navigation-hover: #333333;' in response.text


def test_event_css_reads_each_header_setting_once(rf):
    request = rf.get('/settings.css')
    request.event = make_event(
        header_background_color='#ffee00',
        header_text_color='#111111',
        navigation_text_color='#222222',
        menu_text_scroll_over_color='#333333',
    )

    response = event_css(request)

    assert response.status_code == 200
    assert request.event.settings.lookups == {
        'header_background_color': 1,
        'header_text_color': 1,
        'navigation_text_color': 1,
        'menu_text_scroll_over_color': 1,
        'primary_font': 1,
    }


def test_event_css_etag_changes_when_header_colors_change(rf):
    request = rf.get('/settings.css')
    request.event = make_event()

    default_etag = color_etag(request)
    request.event = make_event(header_background_color='#ffee00')

    assert color_etag(request) != default_etag


def test_event_css_etag_returns_none_string_when_no_colors_are_set(rf):
    request = rf.get('/settings.css')
    request.event = make_event(primary_color='')

    assert color_etag(request) == 'none'


def test_schedule_messages_caches_per_language(rf):
    cache.clear()
    try:
        # 1. Chinese request
        with translation.override('zh-hans'):
            req_zh = rf.get('/widget/messages.js', HTTP_ACCEPT_LANGUAGE='zh-CN,zh;q=0.9')
            res_zh = schedule_messages(req_zh)
            assert res_zh.status_code == 200
            assert 'Accept-Language' in res_zh.get('Vary', '')
            assert 'Cookie' in res_zh.get('Vary', '')
            data_zh = json.loads(
                res_zh.content.decode().replace('const PRETALX_MESSAGES = ', '').rstrip(';')
            )
            assert data_zh['search'] == '搜索'
            assert data_zh['yes'] == '是'

        # 2. English request - must get English, not Chinese cached response
        with translation.override('en'):
            req_en = rf.get('/widget/messages.js', HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9')
            res_en = schedule_messages(req_en)
            assert res_en.status_code == 200
            assert 'Accept-Language' in res_en.get('Vary', '')
            assert 'Cookie' in res_en.get('Vary', '')
            data_en = json.loads(
                res_en.content.decode().replace('const PRETALX_MESSAGES = ', '').rstrip(';')
            )
            assert data_en['search'] == 'Search'
            assert data_en['yes'] == 'Yes'
    finally:
        cache.clear()


def test_pretalx_messages_script_tag_includes_version():
    request = SimpleNamespace(
        user=SimpleNamespace(is_anonymous=True, is_authenticated=False),
        event=SimpleNamespace(urls=SimpleNamespace(schedule='https://example.com/schedule/')),
    )
    rendered = render_to_string('agenda/includes/pretalx_messages_script.html', {'request': request})
    assert 'widget/messages.js?v=10' in rendered


def test_export_schedule_html_event_urls_includes_versioned_messages_js(mocker):
    fake_urls = SimpleNamespace(
        base='https://test/base/',
        schedule='https://test/schedule/',
        schedule_nojs='https://test/schedule/nojs/',
        schedule_widget_data='https://test/schedule/widget/data/',
        featured='https://test/schedule/featured/',
        talks='https://test/schedule/talks/',
        speakers='https://test/schedule/speakers/',
        changelog='https://test/schedule/changelog/',
        feed='https://test/schedule/feed/',
    )
    fake_event = SimpleNamespace(
        urls=fake_urls,
        schedules=mocker.MagicMock(filter=mocker.MagicMock(return_value=[])),
        talks=[],
        speakers=[],
    )
    mocker.patch(
        'eventyay.agenda.management.commands.export_schedule_html.register_data_exporters.send',
        return_value=[],
    )

    urls = list(event_urls(fake_event))
    assert 'https://test/schedule/widget/messages.js?v=10' in urls


