"""Every page layout sets the page language on <html> (issue #6840)."""

import re

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation

from eventyay.base.views.errors import server_error
from eventyay.helpers.i18n import get_html_locale


User = get_user_model()

HTML_LANG = re.compile(r'<html lang=["\']([^"\']+)["\']')


def _lang_of(html):
    match = HTML_LANG.search(html)
    assert match, 'the <html> tag has no lang attribute'
    return match.group(1)


def _html_lang(response):
    return _lang_of(response.content.decode())


def _login(client, locale):
    user = User.objects.create_user(email=f'lang-{locale}@example.com', password='testpass123', locale=locale)
    client.force_login(user)
    return client


@pytest.fixture
def user_client(client, db):
    return _login(client, 'en')


@pytest.mark.parametrize(
    ('language', 'expected'),
    [('en', 'en'), ('de', 'de'), ('de-formal', 'de'), ('ja-jp', 'ja'), ('fa-ir', 'fa-IR')],
)
def test_get_html_locale_uses_public_code(language, expected):
    with translation.override(language):
        assert get_html_locale() == expected


def test_get_html_locale_falls_back_to_default_language_when_translation_is_off():
    with translation.override(None):
        assert get_html_locale() == settings.LANGUAGE_CODE


def test_get_html_locale_keeps_unknown_language_code(monkeypatch):
    monkeypatch.setattr(translation, 'get_language', lambda: 'xx-unknown')
    assert get_html_locale() == 'xx-unknown'


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', ['auth.login', 'account_signup'])
def test_auth_pages_set_html_lang(client, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code == 200
    assert _html_lang(response) == 'en'


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', ['auth.login', 'account_signup'])
def test_auth_pages_follow_selected_language(client, url_name):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'de'
    response = client.get(reverse(url_name))
    assert response.status_code == 200
    assert _html_lang(response) == 'de'


def test_common_dashboard_sets_html_lang(user_client):
    response = user_client.get(reverse('eventyay_common:dashboard'))
    assert response.status_code == 200
    assert _html_lang(response) == 'en'


@pytest.mark.django_db
def test_not_found_page_sets_html_lang(client):
    response = client.get('/this-page-does-not-exist-6840/')
    assert response.status_code == 404
    assert _html_lang(response) == 'en'


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', ['auth.login', 'account_signup'])
def test_rtl_language_sets_lang_and_dir(client, url_name):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'ar'
    response = client.get(reverse(url_name))
    assert re.search(r"<html lang='ar' dir='rtl'", response.content.decode())


@pytest.mark.django_db
def test_orga_auth_page_sets_lang_and_dir_for_rtl(client):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'ar'
    response = client.get(reverse('orga:auth.reset'))
    assert response.status_code == 200
    assert re.search(r"<html lang='ar' dir='rtl'", response.content.decode())


@pytest.mark.django_db
def test_common_dashboard_follows_user_locale(client):
    response = _login(client, 'de').get(reverse('eventyay_common:dashboard'))
    assert response.status_code == 200
    assert _html_lang(response) == 'de'


@pytest.mark.django_db
def test_not_found_page_follows_selected_language(client):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'de'
    response = client.get('/this-page-does-not-exist-6840/')
    assert response.status_code == 404
    assert _html_lang(response) == 'de'


def test_error_page_without_request_context_falls_back_to_en():
    assert _lang_of(render_to_string('500.html')) == 'en'


def test_server_error_page_follows_active_language(rf):
    with translation.override('de'):
        response = server_error(rf.get('/'))
    assert response.status_code == 500
    assert _html_lang(response) == 'de'
