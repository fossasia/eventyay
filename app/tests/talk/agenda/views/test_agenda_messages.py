import json
from types import SimpleNamespace

from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings
from django.utils import translation

from eventyay.agenda.views.schedule import schedule_messages


LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'agenda-messages-cache-tests',
    }
}


def _parse_messages(response):
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/javascript'
    prefix = 'const PRETALX_MESSAGES = '
    content = response.content.decode('utf-8').strip()
    assert content.startswith(prefix)
    assert content.endswith(';')
    json_str = content[len(prefix) : -1]
    return json.loads(json_str)


def test_schedule_messages_default_en(rf: RequestFactory):
    request = rf.get('/widget/messages.js')
    response = schedule_messages(request)
    messages = _parse_messages(response)

    assert messages['add_to_calendar'] == 'Add to Calendar'
    assert messages['speakers'] == 'Speakers'
    assert 'Accept-Language' in response.headers.get('Vary', '')


def test_schedule_messages_locale_zh_hans(rf: RequestFactory):
    request = rf.get('/widget/messages.js?locale=zh-hans')
    response = schedule_messages(request)
    messages = _parse_messages(response)

    assert messages['add_to_calendar'] == '添加到日历'
    assert messages['speakers'] == '演讲者'


def test_schedule_messages_lang_param_zh_hans(rf: RequestFactory):
    request = rf.get('/widget/messages.js?lang=zh-hans')
    response = schedule_messages(request)
    messages = _parse_messages(response)

    assert messages['add_to_calendar'] == '添加到日历'
    assert messages['speakers'] == '演讲者'


def test_schedule_messages_invalid_locale_fallback(rf: RequestFactory):
    # When active language is English (default), invalid locale falls back to English
    request = rf.get('/widget/messages.js?locale=nonexistent-locale-en')
    response = schedule_messages(request)
    messages = _parse_messages(response)

    assert messages['add_to_calendar'] == 'Add to Calendar'
    assert messages['speakers'] == 'Speakers'

    # When active language is non-English, invalid locale preserves the active language context
    with translation.override('de'):
        request_de = rf.get('/widget/messages.js?locale=nonexistent-locale-de')
        response_de = schedule_messages(request_de)
        messages_de = _parse_messages(response_de)

        assert messages_de['add_to_calendar'] == 'Zum Kalender hinzufügen'
        assert messages_de['speakers'] == 'Redner'


@override_settings(CACHES=LOCMEM_CACHE)
def test_schedule_messages_cache_isolation_between_locales(rf: RequestFactory):
    cache.clear()
    try:
        # Call en first
        req_en = rf.get('/widget/messages.js?locale=en')
        resp_en1 = schedule_messages(req_en)
        assert _parse_messages(resp_en1)['add_to_calendar'] == 'Add to Calendar'

        # Call zh-hans next
        req_zh = rf.get('/widget/messages.js?locale=zh-hans')
        resp_zh = schedule_messages(req_zh)
        assert _parse_messages(resp_zh)['add_to_calendar'] == '添加到日历'

        # Call en again, ensuring zh-hans cached value does not leak into en
        resp_en2 = schedule_messages(req_en)
        assert _parse_messages(resp_en2)['add_to_calendar'] == 'Add to Calendar'
        assert _parse_messages(resp_en2)['speakers'] == 'Speakers'
    finally:
        cache.clear()


def test_pretalx_messages_script_template_rendering():
    event = SimpleNamespace(urls=SimpleNamespace(schedule='https://eventyay.com/ev/test/schedule/'))

    # With LANGUAGE_CODE = 'en'
    req_en = SimpleNamespace(
        event=event,
        user=SimpleNamespace(is_anonymous=True, is_authenticated=False),
        LANGUAGE_CODE='en',
    )
    rendered_en = render_to_string('agenda/includes/pretalx_messages_script.html', {'request': req_en})
    assert 'src="https://eventyay.com/ev/test/schedule/widget/messages.js?locale=en"' in rendered_en

    # With LANGUAGE_CODE = 'zh-hans'
    req_zh = SimpleNamespace(
        event=event,
        user=SimpleNamespace(is_anonymous=True, is_authenticated=False),
        LANGUAGE_CODE='zh-hans',
    )
    rendered_zh = render_to_string('agenda/includes/pretalx_messages_script.html', {'request': req_zh})
    assert 'src="https://eventyay.com/ev/test/schedule/widget/messages.js?locale=zh-hans"' in rendered_zh

    # Without LANGUAGE_CODE (fallback)
    req_none = SimpleNamespace(
        event=event,
        user=SimpleNamespace(is_anonymous=True, is_authenticated=False),
        LANGUAGE_CODE='',
    )
    rendered_none = render_to_string('agenda/includes/pretalx_messages_script.html', {'request': req_none})
    assert 'src="https://eventyay.com/ev/test/schedule/widget/messages.js"' in rendered_none
