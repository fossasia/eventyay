import json
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup
from django import forms as dj_forms
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string

from eventyay.base.forms import I18nMarkdownTextarea
from eventyay.base.models.page import Page
from eventyay.common.context_processors import system_information
from eventyay.control.forms import MultipleLanguagesWidget
from eventyay.control.forms.global_settings import GlobalSettingsForm
from eventyay.control.views.pages import SystemPageView


def _make_mock_settings(stored=None):
    # Mock settings store matching hierarkey get(key, default=None, as_type=None) signature
    data = dict(stored or {})
    mock_settings = MagicMock()
    mock_settings._parent = None
    mock_settings._h = MagicMock()
    mock_settings._h.defaults = {}
    mock_settings._h.attribute_name = 'settings'
    mock_settings._h.get_declared_type.return_value = str

    def _get(key, default=None, as_type=None, **kwargs):
        val = data.get(key)
        if val is None:
            val = default if default is not None else kwargs.get('default')
        target_type = as_type or kwargs.get('as_type')
        if val is not None and target_type is not None:
            if target_type is bool:
                return val if isinstance(val, bool) else str(val).lower() in ('true', '1', 't')
            if target_type is list:
                if isinstance(val, str):
                    try:
                        return json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        return [val]
                return list(val)
            if target_type is str:
                return str(val)
            try:
                return target_type(val)
            except (ValueError, TypeError):
                return val
        return val

    def _set(key, value):
        data[key] = value

    def _delitem(*args):
        data.pop(args[-1], None)

    mock_settings.get.side_effect = _get
    mock_settings.set.side_effect = _set
    mock_settings.__delitem__ = _delitem
    mock_settings._cache.side_effect = lambda: dict(data)
    mock_settings.freeze.side_effect = lambda: dict(data)
    return mock_settings


def test_global_settings_form_footer_defaults():
    # Verify all expected footer link and page fields are registered
    with patch('eventyay.control.forms.global_settings.GlobalSettingsObject') as mock_gso:
        mock_gso.return_value.settings = _make_mock_settings()
        form = GlobalSettingsForm()
        for key in ['events', 'terms', 'privacy', 'pricing', 'documentation', 'support']:
            assert f'footer_link_{key}_enabled' in form.fields
            assert f'footer_link_{key}_url' in form.fields
        for page_key in ['terms', 'privacy', 'pricing', 'support']:
            assert f'footer_page_{page_key}_text' in form.fields


def test_global_settings_form_has_page_locales_field():
    # Verify page_locales field configuration and widget type
    with patch('eventyay.control.forms.global_settings.GlobalSettingsObject') as mock_gso:
        mock_gso.return_value.settings = _make_mock_settings()
        form = GlobalSettingsForm()
        assert 'page_locales' in form.fields
        assert isinstance(form.fields['page_locales'].widget, MultipleLanguagesWidget)
        assert form.initial.get('page_locales') == ['en']


def test_page_locales_in_pages_field_group():
    # Verify page_locales is the first field in the pages tab group
    with patch('eventyay.control.forms.global_settings.GlobalSettingsObject') as mock_gso:
        mock_gso.return_value.settings = _make_mock_settings()
        form = GlobalSettingsForm()
        pages_group = next((fnames for key, _, fnames in form.field_groups if key == 'pages'), None)
        assert pages_group is not None
        assert pages_group[0] == 'page_locales'


def test_page_locales_defaults_to_english():
    # Verify default page locales sets initial to English
    with patch('eventyay.control.forms.global_settings.GlobalSettingsObject') as mock_gso:
        mock_gso.return_value.settings = _make_mock_settings()
        form = GlobalSettingsForm()
        assert form.initial.get('page_locales') == ['en']


def test_page_locales_preserves_saved_value():
    # Verify saved page locales are loaded into form initial
    with patch('eventyay.control.forms.global_settings.GlobalSettingsObject') as mock_gso:
        mock_gso.return_value.settings = _make_mock_settings({
            'page_locales': json.dumps(['en', 'de']),
        })
        form = GlobalSettingsForm()
        assert form.initial.get('page_locales') == ['en', 'de']


def test_page_locales_auto_includes_existing_content_locales():
    # Verify existing translations are auto-included in page locales initial
    with patch('eventyay.control.forms.global_settings.GlobalSettingsObject') as mock_gso:
        mock_gso.return_value.settings = _make_mock_settings({
            'page_locales': json.dumps(['en']),
            'footer_page_terms_text': json.dumps({'en': 'Terms', 'fr': 'Conditions'}),
        })
        form = GlobalSettingsForm()
        assert set(form.initial.get('page_locales')) == {'en', 'fr'}


def test_global_settings_form_save_persists_page_locales():
    # Verify full form validation and save cycle persists page_locales
    mock_settings = _make_mock_settings({'page_locales': json.dumps(['en'])})
    with patch('eventyay.control.forms.global_settings.GlobalSettingsObject') as mock_gso:
        mock_gso.return_value.settings = mock_settings
        unbound = GlobalSettingsForm()
        post_data = {k: v for k, v in unbound.initial.items() if v is not None}
        post_data['page_locales'] = ['en', 'de', 'es']
        form = GlobalSettingsForm(data=post_data)
        assert form.is_valid(), form.errors
        form.save()
        saved = mock_settings.get('page_locales')
        assert (json.loads(saved) if isinstance(saved, str) else saved) == ['en', 'de', 'es']


def test_i18n_markdown_textarea_renders_all_locales():
    # Verify widget renders all configured locales with data-lang attributes
    field = dj_forms.CharField()
    widget = I18nMarkdownTextarea(locales=['en', 'de', 'fr'], field=field)

    html = widget.render('test_field', {'en': 'Hello', 'de': 'Hallo', 'fr': 'Bonjour'}, attrs={'id': 'id_test'})
    assert 'data-lang="en"' in html
    assert 'data-lang="de"' in html
    assert 'data-lang="fr"' in html
    assert 'placeholder="English"' in html
    assert 'placeholder="German"' in html


def test_context_processor_core_footer_links(rf):
    # Verify system_information context processor populates core footer links
    request = rf.get('/')
    with patch('eventyay.common.context_processors.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings({
            'footer_link_events_enabled': True,
            'footer_link_terms_enabled': True,
            'footer_link_privacy_enabled': True,
            'footer_link_pricing_enabled': True,
            'footer_link_documentation_enabled': True,
            'footer_link_support_enabled': True,
        })
        mock_gso.return_value.settings = mock_settings
        ctx = system_information(request)
        assert 'core_footer_links' in ctx
        keys = [link['key'] for link in ctx['core_footer_links']]
        for expected in ['events', 'terms', 'privacy', 'pricing', 'documentation', 'support']:
            assert expected in keys


def test_context_processor_excludes_disabled_footer_links(rf):
    # Verify disabled footer links are excluded from context processor output
    request = rf.get('/')
    with patch('eventyay.common.context_processors.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings({
            'footer_link_events_enabled': True,
            'footer_link_terms_enabled': False,
            'footer_link_privacy_enabled': True,
            'footer_link_pricing_enabled': False,
            'footer_link_documentation_enabled': True,
            'footer_link_support_enabled': False,
        })
        mock_gso.return_value.settings = mock_settings
        ctx = system_information(request)
        keys = [link['key'] for link in ctx['core_footer_links']]
        assert 'terms' not in keys
        assert 'pricing' not in keys
        assert 'support' not in keys
        assert 'events' in keys
        assert 'privacy' in keys
        assert 'documentation' in keys


def test_system_page_view_slug_handling():
    # Verify SystemPageView resolves slug from attribute and URL kwargs
    view = SystemPageView()
    view.slug = 'terms'
    assert view.get_slug() == 'terms'

    view_kwargs = SystemPageView()
    view_kwargs.kwargs = {'slug': 'privacy'}
    assert view_kwargs.get_slug() == 'privacy'

    with patch('eventyay.control.views.pages.Page.objects.get') as mock_get:
        mock_page_terms = MagicMock(title='Terms of Service', slug='terms')
        mock_page_privacy = MagicMock(title='Privacy Policy', slug='privacy')
        mock_get.side_effect = lambda slug: mock_page_privacy if slug == 'privacy' else mock_page_terms

        assert view.get_page() == mock_page_terms
        assert view_kwargs.get_page() == mock_page_privacy


def test_system_page_view_custom_content():
    # Verify SystemPageView falls back to custom global setting content
    view = SystemPageView()
    view.slug = 'privacy'

    with patch('eventyay.control.views.pages.Page.objects.get', side_effect=Page.DoesNotExist):
        with patch('eventyay.control.views.pages.GlobalSettingsObject') as mock_gso:
            mock_settings = _make_mock_settings({
                'footer_page_privacy_text': '# Custom Privacy Content',
            })
            mock_gso.return_value.settings = mock_settings
            page = view.get_page()
            assert page.title == 'Privacy Policy'
            assert str(page.text) == '# Custom Privacy Content'


def test_core_footer_template_structure():
    # Verify core footer template renders links and handles external targets
    sample_links = [
        {'key': 'events', 'label': 'Events', 'url': '/upcoming', 'target_blank': False},
        {'key': 'terms', 'label': 'Terms', 'url': '/terms', 'target_blank': False},
        {'key': 'documentation', 'label': 'Documentation', 'url': 'https://docs.eventyay.com', 'target_blank': True},
    ]
    html = render_to_string('common/includes/core_footer.html', {'core_footer_links': sample_links})
    soup = BeautifulSoup(html, 'html.parser')

    assert soup.find('nav', class_='core-footer-nav') is not None
    assert soup.find('div', class_='core-footer-links-container') is not None

    events_a = soup.find('a', href=lambda h: h and 'upcoming' in h)
    assert events_a is not None
    assert events_a.get_text(strip=True) == 'Events'
    assert events_a.get('target') != '_blank'

    terms_a = soup.find('a', href=lambda h: h and 'terms' in h)
    assert terms_a is not None
    assert terms_a.get_text(strip=True) == 'Terms'
    assert terms_a.get('target') != '_blank'

    docs_a = soup.find('a', href=lambda h: h and 'docs.eventyay.com' in h)
    assert docs_a is not None
    assert docs_a.get_text(strip=True) == 'Documentation'
    assert docs_a.get('target') == '_blank'
    rel = docs_a.get('rel', [])
    assert 'noopener' in (rel if isinstance(rel, list) else rel.split())


def test_footer_context_renders_correctly(rf):
    # Verify template renders correctly from real context processor output
    request = rf.get('/')
    with patch('eventyay.common.context_processors.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings({
            'footer_link_events_enabled': True,
            'footer_link_terms_enabled': True,
            'footer_link_documentation_enabled': True,
        })
        mock_gso.return_value.settings = mock_settings
        ctx = system_information(request)
        html = render_to_string('common/includes/core_footer.html', ctx)
        soup = BeautifulSoup(html, 'html.parser')
        assert soup.find('a', href=lambda h: h and 'upcoming' in h) is not None
        assert soup.find('a', href=lambda h: h and 'terms' in h) is not None
        assert soup.find('a', href=lambda h: h and 'docs.eventyay.com' in h) is not None


def test_public_pages_base_template_unauthenticated(rf):
    # Verify public page shell renders language switcher, login link, and no sidebar for guests
    request = rf.get('/terms/')
    request.user = AnonymousUser()
    request.LANGUAGE_CODE = 'en'

    context = {
        'request': request,
        'page': MagicMock(title='Terms of Service'),
        'content': '<p>Terms content</p>',
        'nav_items': [],
        'staff_session': False,
        'language_options': [{'code': 'en', 'label': 'English'}, {'code': 'de', 'label': 'Deutsch'}],
        'core_footer_links': [],
        'django_settings': settings,
    }
    html = render_to_string('pretixcontrol/admin/pages/show.html', context)
    soup = BeautifulSoup(html, 'html.parser')

    assert soup.find('details', id='language-dropdown') is not None
    assert soup.find('a', href=lambda h: h and 'login' in h) is not None
    assert soup.find('details', id='profile-dropdown') is None
    assert soup.find('aside', id='startpage-sidebar') is None


def test_public_pages_base_template_authenticated(rf):
    # Verify public page shell renders language switcher, profile dropdown, and sidebar for logged-in users
    request = rf.get('/terms/')
    user = MagicMock(is_authenticated=True, is_staff=False, email='user@eventyay.com', fullname='Test User')
    request.user = user
    request.LANGUAGE_CODE = 'en'

    nav_items = [
        {'label': 'My Orders', 'url': '/common/orders/', 'active': False, 'icon': 'shopping-cart'},
        {'label': 'My Events', 'url': '/common/events/', 'active': False, 'icon': 'calendar'},
    ]
    context = {
        'request': request,
        'page': MagicMock(title='Terms of Service'),
        'content': '<p>Terms content</p>',
        'nav_items': nav_items,
        'staff_session': False,
        'language_options': [{'code': 'en', 'label': 'English'}, {'code': 'de', 'label': 'Deutsch'}],
        'core_footer_links': [],
        'django_settings': settings,
    }
    html = render_to_string('pretixcontrol/admin/pages/show.html', context)
    soup = BeautifulSoup(html, 'html.parser')

    assert soup.find('details', id='language-dropdown') is not None
    assert soup.find('details', id='profile-dropdown') is not None
    assert soup.find('button', id='sidebar-toggle') is not None
    sidebar = soup.find('aside', id='startpage-sidebar')
    assert sidebar is not None
    assert soup.find('a', href=lambda h: h and '/common/orders/' in h) is not None

