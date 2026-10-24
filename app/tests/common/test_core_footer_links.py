import json
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup
from django import forms as dj_forms
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.http import Http404
from django.template.loader import render_to_string

from eventyay.base.models.page import (
    get_visible_start_page_pages,
    get_visible_system_pages,
    is_builtin_page_url,
    is_content_empty,
    is_external_url,
    is_system_page_configured,
    validate_footer_url,
)
from eventyay.common.context_processors import system_information
from eventyay.common.forms.fields import I18nRichTextFormField
from eventyay.common.forms.widgets import I18nRichTextWidget
from eventyay.control.forms.pages_admin import DefaultPageContentForm, FooterContentForm
from eventyay.control.views.pages import ShowPageView, SystemPageView


def _make_mock_settings(stored=None):
    """Create a mock settings store matching hierarkey get/set signature."""
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


def _render_page_template(template_name, context, request=None):
    """Render a template with privacy consent and event signals safely mocked for unit tests."""
    mock_gso = MagicMock()
    mock_gso.settings.get.return_value = None
    with (
        patch('eventyay.base.templatetags.privacy_consent.GlobalSettingsObject', return_value=mock_gso),
        patch('eventyay.base.templatetags.privacy_consent.external_cmp_script', return_value=''),
        patch('eventyay.base.templatetags.privacy_consent.consent_config', return_value='{}'),
        patch('eventyay.base.templatetags.privacy_consent.consent_provider', return_value='disabled'),
        patch('eventyay.base.templatetags.privacy_consent.cookie_policy_url', return_value=''),
        patch('eventyay.base.templatetags.privacy_consent.build_consent_config', return_value=None),
        patch('eventyay.common.signals.user_dashboard_links.send', return_value=[]),
    ):
        return render_to_string(template_name, context, request=request)


def test_footer_content_form_footer_defaults():
    """Verify all expected footer link and page fields are registered on pages admin forms."""
    mock_obj = MagicMock()
    mock_obj.settings = _make_mock_settings()
    form = FooterContentForm(obj=mock_obj)
    for key in ['events', 'terms', 'privacy', 'pricing', 'documentation', 'support']:
        assert f'footer_link_{key}_enabled' in form.fields
        assert f'footer_link_{key}_url' in form.fields
    for page_key in ['terms', 'privacy', 'support']:
        page_form = DefaultPageContentForm(obj=mock_obj, slug=page_key)
        field_name = f'footer_page_{page_key}_text'
        assert field_name in page_form.fields
        assert isinstance(page_form.fields[field_name], I18nRichTextFormField)
        assert isinstance(page_form.fields[field_name].widget, I18nRichTextWidget)


def test_page_content_form_has_page_locales_field():
    """Verify page_locales field configuration and widget type on pages admin forms."""
    mock_obj = MagicMock()
    mock_obj.settings = _make_mock_settings()
    form = FooterContentForm(obj=mock_obj)
    assert 'page_locales' in form.fields
    assert isinstance(form.fields['page_locales'].widget, dj_forms.MultipleHiddenInput)
    assert form.initial.get('page_locales') == ['en']


def test_page_locales_defaults_to_english():
    """Verify default page locales sets initial to English."""
    mock_obj = MagicMock()
    mock_obj.settings = _make_mock_settings()
    form = FooterContentForm(obj=mock_obj)
    assert form._page_locales == ['en']


def test_page_locales_preserves_saved_value():
    """Verify saved page locales are loaded into form initial."""
    mock_obj = MagicMock()
    mock_obj.settings = _make_mock_settings(
        {
            'page_locales': json.dumps(['en', 'de']),
        }
    )
    form = FooterContentForm(obj=mock_obj)
    assert form._page_locales == ['en', 'de']


def test_page_locales_auto_includes_existing_content_locales():
    """Verify existing translations are auto-included in page locales initial."""
    mock_obj = MagicMock()
    mock_obj.settings = _make_mock_settings(
        {
            'page_locales': json.dumps(['en']),
            'footer_page_terms_text': json.dumps({'en': 'Terms', 'fr': 'Conditions'}),
        }
    )
    form = DefaultPageContentForm(obj=mock_obj, slug='terms')
    assert set(form._page_locales) == {'en', 'fr'}


def test_page_content_form_save_persists_page_locales():
    """Verify full form validation and save cycle persists page_locales."""
    mock_settings = _make_mock_settings({'page_locales': json.dumps(['en'])})
    mock_obj = MagicMock()
    mock_obj.settings = mock_settings
    unbound = FooterContentForm(obj=mock_obj)
    post_data = {k: v for k, v in unbound.initial.items() if v is not None}
    post_data['page_locales'] = ['en', 'de', 'es']
    form = FooterContentForm(obj=mock_obj, data=post_data)
    assert form.is_valid(), form.errors
    form.save()
    saved = mock_settings.get('page_locales')
    assert (json.loads(saved) if isinstance(saved, str) else saved) == ['en', 'de', 'es']


def test_i18n_richtext_widget_renders_all_locales():
    """Verify widget renders all configured locales with data-lang, tiptap wrapper and profile."""
    field = dj_forms.CharField()
    widget = I18nRichTextWidget(locales=['en', 'de', 'fr'], field=field)

    html = widget.render(
        'test_field', {'en': '<p>Hello</p>', 'de': '<p>Hallo</p>', 'fr': '<p>Bonjour</p>'}, attrs={'id': 'id_test'}
    )
    assert 'data-lang="en"' in html
    assert 'data-lang="de"' in html
    assert 'data-lang="fr"' in html
    assert 'data-tiptap-wrapper="true"' in html
    assert 'data-tiptap-profile="richtext"' in html
    assert 'id="id_test_0"' in html
    assert 'id="id_test_1"' in html
    assert 'id="id_test_2"' in html


def test_i18n_richtext_form_field_sanitizes():
    """Verify I18nRichTextFormField sanitizes malicious HTML tags."""
    from i18nfield.strings import LazyI18nString

    field = I18nRichTextFormField(locales=['en', 'de'], required=False)
    result = field.clean(['<p>Terms</p><script>alert(1)</script>', '<p>Bedingungen</p>'])
    assert isinstance(result, LazyI18nString)
    assert result.data['en'] == '<p>Terms</p>'
    assert result.data['de'] == '<p>Bedingungen</p>'


def test_context_processor_core_footer_links(rf):
    """Verify system_information context processor populates core footer links."""
    request = rf.get('/')
    with patch('eventyay.common.context_processors.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings(
            {
                'footer_link_events_enabled': True,
                'footer_link_terms_enabled': True,
                'footer_page_terms_text': 'Terms text',
                'footer_link_privacy_enabled': True,
                'footer_page_privacy_text': 'Privacy text',
                'footer_link_pricing_enabled': True,
                'footer_link_pricing_url': 'https://eventyay.com/pricing',
                'footer_page_pricing_text': 'Pricing text',
                'footer_link_documentation_enabled': True,
                'footer_link_support_enabled': True,
                'footer_page_support_text': 'Support text',
            }
        )
        mock_gso.return_value.settings = mock_settings
        ctx = system_information(request)
        assert 'core_footer_links' in ctx
        keys = [link['key'] for link in ctx['core_footer_links']]
        for expected in ['events', 'terms', 'privacy', 'pricing', 'documentation', 'support']:
            assert expected in keys


def test_context_processor_excludes_disabled_footer_links(rf):
    """Verify disabled footer links are excluded from context processor output."""
    request = rf.get('/')
    with patch('eventyay.common.context_processors.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings(
            {
                'footer_link_events_enabled': True,
                'footer_link_terms_enabled': False,
                'footer_page_terms_text': 'Terms text',
                'footer_link_privacy_enabled': True,
                'footer_page_privacy_text': 'Privacy text',
                'footer_link_pricing_enabled': False,
                'footer_page_pricing_text': 'Pricing text',
                'footer_link_documentation_enabled': True,
                'footer_link_support_enabled': False,
                'footer_page_support_text': 'Support text',
            }
        )
        mock_gso.return_value.settings = mock_settings
        ctx = system_information(request)
        keys = [link['key'] for link in ctx['core_footer_links']]
        assert 'terms' not in keys
        assert 'pricing' not in keys
        assert 'support' not in keys
        assert 'events' in keys
        assert 'privacy' in keys
        assert 'documentation' in keys


def test_context_processor_excludes_unconfigured_footer_links(rf):
    """Verify unconfigured system pages are excluded from core footer links."""
    request = rf.get('/')
    with patch('eventyay.common.context_processors.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings(
            {
                'footer_link_events_enabled': True,
                'footer_link_terms_enabled': True,
                # terms text is not configured
                'footer_link_privacy_enabled': True,
                'footer_page_privacy_text': 'Privacy configured',
                'footer_link_documentation_enabled': True,
            }
        )
        mock_gso.return_value.settings = mock_settings
        with patch('eventyay.base.models.page.Page.objects.filter') as mock_filter:
            mock_filter.return_value = []
            ctx = system_information(request)
            keys = [link['key'] for link in ctx['core_footer_links']]
            assert 'terms' not in keys
            assert 'privacy' in keys
            assert 'events' in keys
            assert 'documentation' in keys


def test_context_processor_handles_external_and_same_site_footer_urls(rf):
    """Verify external destinations remain visible without local content, while same-site absolute URLs are checked."""
    request = rf.get('/')
    with patch('django.conf.settings.SITE_URL', 'https://eventyay.com'):
        with patch('django.conf.settings.SITE_NETLOC', 'eventyay.com'):
            with patch('eventyay.common.context_processors.GlobalSettingsObject') as mock_gso:
                mock_settings = _make_mock_settings(
                    {
                        'footer_link_events_enabled': True,
                        # Terms points to an external site, local content is unconfigured
                        'footer_link_terms_enabled': True,
                        'footer_link_terms_url': 'HTTP://EXTERNAL-LEGAL.COM/terms',
                        # Privacy points to a same-site absolute URL, local content is unconfigured
                        'footer_link_privacy_enabled': True,
                        'footer_link_privacy_url': 'https://eventyay.com/privacy',
                        # Pricing points to a same-site absolute URL, local content IS configured
                        'footer_link_pricing_enabled': True,
                        'footer_link_pricing_url': 'https://eventyay.com/pricing',
                        'footer_page_pricing_text': 'Pricing info',
                    }
                )
                mock_gso.return_value.settings = mock_settings
                with patch('eventyay.base.models.page.Page.objects.filter') as mock_filter:
                    mock_filter.return_value = []
                    ctx = system_information(request)
                    links_by_key = {link['key']: link for link in ctx['core_footer_links']}

                    # External terms link is NOT hidden
                    assert 'terms' in links_by_key
                    assert links_by_key['terms']['url'] == 'HTTP://EXTERNAL-LEGAL.COM/terms'
                    assert links_by_key['terms']['target_blank'] is True

                    # Same-site unconfigured privacy link IS hidden
                    assert 'privacy' not in links_by_key

                    # Same-site configured pricing link is shown, not target_blank
                    assert 'pricing' in links_by_key
                    assert links_by_key['pricing']['target_blank'] is False


def test_system_page_view_slug_handling():
    """Verify SystemPageView resolves slug from attribute and URL kwargs."""
    view = SystemPageView()
    view.slug = 'terms'
    assert view.get_slug() == 'terms'

    view_kwargs = SystemPageView()
    view_kwargs.kwargs = {'slug': 'privacy'}
    assert view_kwargs.get_slug() == 'privacy'

    with patch('eventyay.control.views.pages.Page.objects.filter') as mock_filter:
        mock_page_terms = MagicMock(title='Terms of Service', slug='terms', text='Terms text')
        mock_page_privacy = MagicMock(title='Privacy Policy', slug='privacy', text='Privacy text')
        mock_filter.side_effect = lambda slug: MagicMock(
            first=lambda: mock_page_privacy if slug == 'privacy' else mock_page_terms
        )
        with patch('eventyay.control.views.pages.GlobalSettingsObject') as mock_gso:
            mock_settings = _make_mock_settings(
                {
                    'footer_link_terms_enabled': True,
                    'footer_link_privacy_enabled': True,
                }
            )
            mock_gso.return_value.settings = mock_settings

            assert view.get_page() == mock_page_terms
            assert view_kwargs.get_page() == mock_page_privacy


def test_system_page_view_custom_content():
    """Verify SystemPageView falls back to custom global setting content."""
    view = SystemPageView()
    view.slug = 'privacy'

    with patch('eventyay.control.views.pages.Page.objects.filter') as mock_filter:
        mock_filter.return_value.first.return_value = None
        with patch('eventyay.control.views.pages.GlobalSettingsObject') as mock_gso:
            mock_settings = _make_mock_settings(
                {
                    'footer_link_privacy_enabled': True,
                    'footer_page_privacy_text': '# Custom Privacy Content',
                }
            )
            mock_gso.return_value.settings = mock_settings
            page = view.get_page()
            assert page.title == 'Privacy Policy'
            assert str(page.text) == '# Custom Privacy Content'


def test_system_page_view_settings_precedence_over_db_page():
    """Verify global settings content takes precedence over database page content for system pages."""
    view = SystemPageView()
    view.slug = 'terms'

    with patch('eventyay.control.views.pages.Page.objects.filter') as mock_filter:
        mock_filter.return_value.first.return_value = MagicMock(title='DB Terms', slug='terms', text='DB terms text')
        with patch('eventyay.control.views.pages.GlobalSettingsObject') as mock_gso:
            mock_settings = _make_mock_settings(
                {
                    'footer_link_terms_enabled': True,
                    'footer_page_terms_text': '# Settings terms text',
                }
            )
            mock_gso.return_value.settings = mock_settings
            page = view.get_page()
            assert page.title == 'Terms of Service'
            assert str(page.text) == '# Settings terms text'


def test_system_page_view_unconfigured_returns_404():
    """Verify SystemPageView raises Http404 when content is unconfigured."""
    view = SystemPageView()
    view.slug = 'terms'

    with patch('eventyay.control.views.pages.Page.objects.filter') as mock_filter:
        mock_filter.return_value.first.return_value = None
        with patch('eventyay.control.views.pages.GlobalSettingsObject') as mock_gso:
            mock_settings = _make_mock_settings(
                {
                    'footer_link_terms_enabled': True,
                }
            )
            mock_gso.return_value.settings = mock_settings
            with pytest.raises(Http404):
                view.get_page()


def test_system_page_view_disabled_returns_404():
    """Verify SystemPageView raises Http404 when page is disabled."""
    view = SystemPageView()
    view.slug = 'terms'

    with patch('eventyay.control.views.pages.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings(
            {
                'footer_link_terms_enabled': False,
                'footer_page_terms_text': '# Terms content',
            }
        )
        mock_gso.return_value.settings = mock_settings
        with pytest.raises(Http404):
            view.get_page()


def test_system_page_view_empty_db_page_returns_404():
    """Verify SystemPageView raises Http404 when database page has empty content."""
    view = SystemPageView()
    view.slug = 'terms'

    with patch('eventyay.control.views.pages.Page.objects.filter') as mock_filter:
        mock_filter.return_value.first.return_value = MagicMock(title='Terms', slug='terms', text='')
        with patch('eventyay.control.views.pages.GlobalSettingsObject') as mock_gso:
            mock_settings = _make_mock_settings(
                {
                    'footer_link_terms_enabled': True,
                }
            )
            mock_gso.return_value.settings = mock_settings
            with pytest.raises(Http404):
                view.get_page()


def test_system_page_view_blank_db_page_serves_settings_text():
    """Verify SystemPageView treats blank DB page as absent and serves settings text."""
    view = SystemPageView()
    view.slug = 'terms'

    with patch('eventyay.control.views.pages.Page.objects.filter') as mock_filter:
        mock_filter.return_value.first.return_value = MagicMock(title='Terms', slug='terms', text='')
        with patch('eventyay.control.views.pages.GlobalSettingsObject') as mock_gso:
            mock_settings = _make_mock_settings(
                {
                    'footer_link_terms_enabled': True,
                    'footer_page_terms_text': '# Terms from settings',
                }
            )
            mock_gso.return_value.settings = mock_settings
            page = view.get_page()
            assert page.title == 'Terms of Service'
            assert str(page.text) == '# Terms from settings'


def test_show_page_view_disabled_system_page_returns_404():
    """Verify ShowPageView enforces enabled check for system-page slugs."""
    view = ShowPageView()
    view.kwargs = {'slug': 'terms'}

    with patch('eventyay.control.views.pages.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings(
            {
                'footer_link_terms_enabled': False,
            }
        )
        mock_gso.return_value.settings = mock_settings
        with pytest.raises(Http404):
            view.get_page()


def test_show_page_view_serves_custom_page():
    """Verify ShowPageView serves non-system custom page normally."""
    view = ShowPageView()
    view.kwargs = {'slug': 'about-us'}

    mock_custom_page = MagicMock(title='About Us', slug='about-us', text='About us content')
    with patch('eventyay.control.views.pages.Page.objects.filter') as mock_filter:
        mock_filter.return_value.first.return_value = mock_custom_page
        page = view.get_page()
        assert page == mock_custom_page


def test_builtin_and_external_url_classification():
    """Verify accurate classification without relying on lowercase prefix checks."""
    with patch('django.conf.settings.SITE_URL', 'https://eventyay.com'):
        with patch('django.conf.settings.SITE_NETLOC', 'eventyay.com'):
            # Built-in relative paths
            assert is_builtin_page_url('/terms', 'terms') is True
            assert is_builtin_page_url('/page/terms/', 'terms') is True
            assert is_external_url('/terms') is False

            # Built-in same-site absolute URLs
            assert is_builtin_page_url('https://eventyay.com/terms', 'terms') is True
            assert is_builtin_page_url('https://eventyay.com/page/terms', 'terms') is True
            assert is_external_url('https://eventyay.com/terms') is False

            # External destinations
            assert is_builtin_page_url('HTTP://EXTERNAL.COM/terms', 'terms') is False
            assert is_external_url('HTTP://EXTERNAL.COM/terms') is True
            assert is_builtin_page_url('//external.com/privacy', 'privacy') is False
            assert is_external_url('//external.com/privacy') is True
            assert is_builtin_page_url('mailto:support@eventyay.com', 'support') is False
            assert is_external_url('mailto:support@eventyay.com') is True


def test_is_content_empty_helper():
    """Verify is_content_empty detects empty values, blank translations, and valid content."""
    from i18nfield.strings import LazyI18nString

    assert is_content_empty(None) is True
    assert is_content_empty('') is True
    assert is_content_empty('   ') is True
    assert is_content_empty('null') is True
    assert is_content_empty('[]') is True
    assert is_content_empty('{}') is True
    assert is_content_empty([]) is True
    assert is_content_empty({}) is True
    assert is_content_empty(['<p></p>']) is True
    assert is_content_empty(LazyI18nString('')) is True
    assert is_content_empty(LazyI18nString({'en': '', 'de': '   '})) is True
    assert is_content_empty('{"en": ""}') is True
    assert is_content_empty('{"en": "Terms of Service"}') is False
    assert is_content_empty(LazyI18nString({'en': 'Terms of Service'})) is False
    assert is_content_empty('# Custom Content') is False


def test_default_page_content_form_field_attributes():
    """Verify DefaultPageContentForm builds enabled toggle with conditional label and help text."""
    mock_obj = MagicMock()
    mock_obj.settings = _make_mock_settings()
    # Content page (terms)
    form = DefaultPageContentForm(obj=mock_obj, slug='terms')
    assert 'footer_link_terms_enabled' in form.fields
    field = form.fields['footer_link_terms_enabled']
    assert str(field.label) == 'Active / Enable page'
    assert '404' in str(field.help_text)

    # Link-only page without content (documentation)
    link_form = DefaultPageContentForm(obj=mock_obj, slug='documentation')
    assert 'footer_link_documentation_enabled' in link_form.fields
    link_field = link_form.fields['footer_link_documentation_enabled']
    assert str(link_field.label) == 'Show in footer'
    assert '404' not in str(link_field.help_text)


def test_core_footer_template_structure():
    """Verify core footer template renders links and handles external targets."""
    sample_links = [
        {'key': 'events', 'label': 'Events', 'url': '/upcoming', 'target_blank': False},
        {'key': 'terms', 'label': 'Terms', 'url': '/terms', 'target_blank': False},
        {'key': 'documentation', 'label': 'Documentation', 'url': 'https://docs.eventyay.com', 'target_blank': True},
    ]
    html = _render_page_template('common/includes/core_footer.html', {'core_footer_links': sample_links})
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
    """Verify template renders correctly from real context processor output."""
    request = rf.get('/')
    with patch('eventyay.common.context_processors.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings(
            {
                'footer_link_events_enabled': True,
                'footer_link_terms_enabled': True,
                'footer_page_terms_text': 'Terms of service content',
                'footer_link_documentation_enabled': True,
            }
        )
        mock_gso.return_value.settings = mock_settings
        with patch('eventyay.base.models.page.Page.objects.filter', return_value=[]):
            ctx = system_information(request)
            html = _render_page_template('common/includes/core_footer.html', ctx)
        soup = BeautifulSoup(html, 'html.parser')
        assert soup.find('a', href=lambda h: h and 'upcoming' in h) is not None
        assert soup.find('a', href=lambda h: h and 'terms' in h) is not None
        assert soup.find('a', href=lambda h: h and 'docs.eventyay.com' in h) is not None


def test_public_pages_base_template_unauthenticated(rf):
    """Verify public page shell renders language switcher, login link, and no sidebar for guests."""
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
    html = _render_page_template('pretixcontrol/admin/pages/show.html', context)
    soup = BeautifulSoup(html, 'html.parser')

    assert soup.find('details', id='language-dropdown') is not None
    assert soup.find('a', href=lambda h: h and 'login' in h) is not None
    assert soup.find('details', id='profile-dropdown') is None
    assert soup.find('aside', id='startpage-sidebar') is None


def test_public_pages_base_template_authenticated(rf):
    """Verify public page shell renders language switcher, profile dropdown, and sidebar for logged-in users."""
    request = rf.get('/terms/')
    user = MagicMock(is_authenticated=True, is_staff=False, email='user@eventyay.com', fullname='Test User')
    user.id = 1
    user.pk = 1
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
    html = _render_page_template('pretixcontrol/admin/pages/show.html', context)
    soup = BeautifulSoup(html, 'html.parser')

    assert soup.find('details', id='language-dropdown') is not None
    assert soup.find('details', id='profile-dropdown') is not None
    assert soup.find('button', id='sidebar-toggle') is not None
    sidebar = soup.find('aside', id='startpage-sidebar')
    assert sidebar is not None
    assert soup.find('a', href=lambda h: h and '/common/orders/' in h) is not None


def test_global_settings_page_preview_form_encoded(rf):
    """Verify page preview endpoint handles form-encoded input data."""
    from eventyay.control.views.global_settings import GlobalSettingsPagePreviewView

    view = GlobalSettingsPagePreviewView.as_view()
    user = MagicMock(
        is_authenticated=True,
        is_staff=True,
        is_administrator=True,
        is_active=True,
        has_active_staff_session=MagicMock(return_value=True),
    )
    request = rf.post(
        '/admin/global/settings/preview/',
        data={'body_en': '<p>Hello <strong>World</strong><script>alert(1)</script></p>', 'body_de': '<p>Hallo</p>'},
    )
    request.user = user
    request.session = MagicMock(session_key='test_session_key')

    response = view(request)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'previews' in data
    assert '<strong>World</strong>' in data['previews']['en']
    assert '<script>' not in data['previews']['en']
    assert '<p>Hallo</p>' in data['previews']['de']


def test_global_settings_page_preview_json_payload(rf):
    """Verify page preview endpoint handles JSON payload and sanitizes script tags."""
    from eventyay.control.views.global_settings import GlobalSettingsPagePreviewView

    view = GlobalSettingsPagePreviewView.as_view()
    user = MagicMock(
        is_authenticated=True,
        is_staff=True,
        is_administrator=True,
        is_active=True,
        has_active_staff_session=MagicMock(return_value=True),
    )
    request = rf.post(
        '/admin/global/settings/preview/',
        data=json.dumps({'html': '<p>Preview text <script>bad()</script></p>'}),
        content_type='application/json',
    )
    request.user = user
    request.session = MagicMock(session_key='test_session_key')

    response = view(request)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'html' in data
    assert '<p>Preview text </p>' in data['html']
    assert '<script>' not in data['html']


def test_is_content_empty_with_rich_text_html():
    """Verify is_content_empty normalizes rich-text HTML values and treats markup-only content as empty."""
    assert is_content_empty('<p></p>') is True
    assert is_content_empty('<p><br></p>') is True
    assert is_content_empty('<p><br/></p>') is True
    assert is_content_empty('<p>&nbsp;</p>') is True
    assert is_content_empty('<p>   </p>') is True
    assert is_content_empty('<p>Actual content</p>') is False
    assert is_content_empty({'en': '<p></p>', 'de': '<p><br></p>'}) is True
    assert is_content_empty({'en': '<p>Actual content</p>', 'de': ''}) is False


def test_validate_footer_url():
    """Verify validate_footer_url accepts valid URLs and paths while rejecting malformed URLs."""
    validate_footer_url('')
    validate_footer_url(None)
    validate_footer_url('/terms')
    validate_footer_url('/page/terms/')
    validate_footer_url('https://docs.eventyay.com')
    validate_footer_url('mailto:support@eventyay.com')

    with pytest.raises(ValidationError):
        validate_footer_url('http://[broken')


def test_url_helpers_malformed_url_safety():
    """Verify is_builtin_page_url and is_external_url handle malformed URLs gracefully without raising ValueError."""
    assert is_builtin_page_url('http://[broken') is False
    assert is_external_url('http://[broken') is False


def test_get_visible_system_pages_excludes_disabled():
    """Verify get_visible_system_pages excludes system pages whose footer link is disabled."""
    mock_qs = MagicMock()
    with patch('eventyay.base.models.page.Page.objects.filter', return_value=mock_qs) as mock_filter:
        mock_settings = _make_mock_settings(
            {
                'footer_link_terms_enabled': False,
                'footer_link_privacy_enabled': True,
                'footer_page_privacy_text': 'Privacy content',
                'footer_page_pricing_text': 'Pricing content',
                'footer_page_support_text': 'Support content',
            }
        )
        get_visible_system_pages('link_in_header', gs=mock_settings)
        mock_filter.assert_called_once_with(link_in_system=True, link_in_header=True)
        mock_qs.exclude.assert_called_once_with(slug__in=['terms'])


def test_get_visible_system_pages_excludes_unconfigured():
    """Verify get_visible_system_pages excludes system pages whose content is not configured."""
    mock_qs = MagicMock()
    with patch('eventyay.base.models.page.Page.objects.filter', return_value=mock_qs) as mock_filter:
        mock_settings = _make_mock_settings(
            {
                'footer_link_terms_enabled': True,
                'footer_link_privacy_enabled': True,
                'footer_page_terms_text': 'Terms content',
                'footer_page_pricing_text': 'Pricing content',
                'footer_page_support_text': 'Support content',
                # privacy is enabled, but has no content in settings
            }
        )
        mock_empty_qs = MagicMock()
        mock_empty_qs.__iter__.return_value = []
        mock_filter.side_effect = [mock_qs, mock_empty_qs]

        get_visible_system_pages('link_in_header', gs=mock_settings)
        mock_qs.exclude.assert_called_once_with(slug__in=['privacy'])


def test_get_visible_start_page_pages_excludes_disabled_and_unconfigured():
    """Verify get_visible_start_page_pages filters by link_on_website_start_page and excludes disabled/unconfigured."""
    mock_qs = MagicMock()
    with patch('eventyay.base.models.page.Page.objects.filter', return_value=mock_qs) as mock_filter:
        mock_settings = _make_mock_settings(
            {
                'footer_link_terms_enabled': False,
                'footer_page_privacy_text': 'Privacy content',
                'footer_page_pricing_text': 'Pricing content',
                'footer_page_support_text': 'Support content',
            }
        )
        get_visible_start_page_pages('link_in_header', gs=mock_settings)
        mock_filter.assert_called_once_with(link_on_website_start_page=True, link_in_header=True)
        mock_qs.exclude.assert_called_once_with(slug__in=['terms'])


def test_footer_content_form_url_validation():
    """Verify FooterContentForm validates URLs and rejects malformed values."""
    mock_obj = MagicMock()
    mock_obj.settings = _make_mock_settings()
    form = FooterContentForm(
        obj=mock_obj,
        data={
            'footer_link_terms_url': 'http://[broken',
        },
    )
    assert not form.is_valid()
    assert 'footer_link_terms_url' in form.errors


def test_default_page_content_form_url_validation():
    """Verify DefaultPageContentForm validates URL field and rejects malformed values."""
    mock_obj = MagicMock()
    mock_obj.settings = _make_mock_settings()
    form = DefaultPageContentForm(
        obj=mock_obj,
        slug='terms',
        data={
            'footer_link_terms_url': 'http://[broken',
        },
    )
    assert not form.is_valid()
    assert 'footer_link_terms_url' in form.errors


def test_is_system_page_configured_with_prefetched_db_pages():
    """Verify is_system_page_configured uses db_pages_with_content set when provided."""
    with patch('eventyay.base.models.page.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings()
        mock_gso.return_value.settings = mock_settings

        with patch('eventyay.base.models.page.Page.objects.filter') as mock_filter:
            # When pre-fetched set includes slug, returns True without querying DB
            assert is_system_page_configured('terms', gs=mock_settings, db_pages_with_content={'terms'}) is True
            mock_filter.assert_not_called()

            # When pre-fetched set does NOT include slug, returns False without querying DB
            assert is_system_page_configured('terms', gs=mock_settings, db_pages_with_content={'privacy'}) is False
            mock_filter.assert_not_called()


def test_context_processor_skips_db_query_when_settings_text_present(rf):
    """Verify system_information does not query Page model when all system pages have settings text."""
    request = rf.get('/')
    with patch('eventyay.common.context_processors.GlobalSettingsObject') as mock_gso:
        mock_settings = _make_mock_settings(
            {
                'footer_link_terms_enabled': True,
                'footer_page_terms_text': 'Terms configured',
                'footer_link_privacy_enabled': True,
                'footer_page_privacy_text': 'Privacy configured',
                'footer_link_pricing_enabled': True,
                'footer_link_pricing_url': 'https://eventyay.com/pricing',
                'footer_page_pricing_text': 'Pricing configured',
                'footer_link_support_enabled': True,
                'footer_page_support_text': 'Support configured',
            }
        )
        mock_gso.return_value.settings = mock_settings
        with patch('eventyay.common.context_processors.Page.objects.filter') as mock_filter:
            ctx = system_information(request)
            mock_filter.assert_not_called()
            keys = [link['key'] for link in ctx['core_footer_links']]
            assert 'terms' in keys
            assert 'privacy' in keys
            assert 'pricing' in keys
            assert 'support' in keys


def test_allowed_netlocs_and_hostname_comparison(rf):
    """Verify _get_allowed_netlocs resolves netlocs and hostnames and url helpers compare both."""
    from eventyay.base.models.page import _get_allowed_netlocs

    request = rf.get('/', HTTP_HOST='eventyay.org:8000')
    with patch('django.conf.settings.ALLOWED_HOSTS', ['*']):
        with patch('django.conf.settings.SITE_URL', 'https://eventyay.com:443'):
            with patch('django.conf.settings.SITE_NETLOC', 'eventyay.com:443'):
                allowed = _get_allowed_netlocs(request)
                assert 'eventyay.com:443' in allowed
                assert 'eventyay.com' in allowed
                assert 'eventyay.org:8000' in allowed
                assert 'eventyay.org' in allowed

                # Verify is_builtin_page_url and is_external_url match hostname even with port
                assert is_builtin_page_url('https://eventyay.org:8000/terms', 'terms', request=request) is True
                assert is_external_url('https://eventyay.org:8000/terms', request=request) is False
                assert is_external_url('https://othersite.com/terms', request=request) is True


def test_form_initialization_does_not_persist_defaults():
    """Verify that initializing Pages admin forms does not persist default values into settings."""
    mock_obj = MagicMock()
    mock_obj.settings = _make_mock_settings()
    form = FooterContentForm(obj=mock_obj)
    # Check that defaults are present in initial but not written via settings.set
    assert form.initial.get('footer_link_terms_enabled') is True
    assert form.initial.get('footer_link_terms_url') == '/terms'
    mock_obj.settings.set.assert_not_called()

    default_form = DefaultPageContentForm(obj=mock_obj, slug='terms')
    assert default_form.initial.get('footer_link_terms_enabled') is True
    assert default_form.initial.get('footer_link_terms_url') == '/terms'
    mock_obj.settings.set.assert_not_called()


def test_validate_footer_url_malformed_ports_and_missing_hosts():
    """Verify validate_footer_url rejects non-numeric ports and HTTP(S) URLs missing a host."""
    with pytest.raises(ValidationError):
        validate_footer_url('https://')

    with pytest.raises(ValidationError):
        validate_footer_url('http://')

    with pytest.raises(ValidationError):
        validate_footer_url('https://example.com:abc/terms')

    # Valid URLs with or without ports must pass without exception
    validate_footer_url('https://example.com:8080/terms')
    validate_footer_url('https://example.com/terms')
    validate_footer_url('/terms')


def test_page_settings_form_rejects_reserved_system_slugs():
    """Verify PageSettingsForm rejects case variants of reserved system page slugs."""
    from eventyay.control.forms.page import PageSettingsForm

    for reserved in ['terms', 'TERMS', 'Privacy', 'support']:
        form = PageSettingsForm(data={'title': 'Test Page', 'slug': reserved})
        assert not form.is_valid()
        assert 'slug' in form.errors
        assert any('reserved' in str(err).lower() for err in form.errors['slug'])


def test_get_page_by_slug_case_and_usable_row_selection():
    """Verify get_page_by_slug normalizes case and selects the first row with non-empty content."""
    from eventyay.base.models.page import Page, get_page_by_slug

    mock_settings = _make_mock_settings(
        {
            'footer_link_terms_enabled': True,
            'footer_page_terms_text': 'Terms from settings',
        }
    )

    # System page requested with uppercase slug returns settings content
    page = get_page_by_slug('TERMS', gs=mock_settings)
    assert page is not None
    assert page.text == 'Terms from settings'

    # When multiple DB rows exist for custom slug, the one with content is chosen
    empty_row = Page(id=1, slug='custom', text='')
    valid_row = Page(id=2, slug='custom', text='Usable content')

    def filter_mock(*args, **kwargs):
        m = MagicMock()
        # When querying for rows with content via exclude, return valid_row
        m.first.return_value = valid_row
        # When first called without exclude, return empty_row
        m_initial = MagicMock()
        m_initial.first.return_value = empty_row
        m_initial.exclude.return_value.exclude.return_value.exclude.return_value = m
        return m_initial

    with patch('eventyay.base.models.page.Page.objects.filter', side_effect=filter_mock):
        custom_page = get_page_by_slug('CUSTOM', gs=mock_settings)
        assert custom_page is not None
        assert custom_page.text == 'Usable content'


def test_signup_confirmation_pages_prefers_settings_text(rf):
    """Verify SignupView.confirmation_pages uses the same precedence as ShowPageView."""
    from eventyay.base.models.page import Page
    from eventyay.eventyay_common.views.custom import SignupView

    view = SignupView()
    view.request = rf.get('/signup')

    db_terms_page = Page(id=1, slug='terms', confirmation_required=True, text='DB old terms')
    mock_qs = MagicMock()
    mock_qs.order_by.return_value = [db_terms_page]

    with patch('eventyay.base.models.page.Page.objects.filter', return_value=mock_qs):
        with patch('eventyay.base.models.page.GlobalSettingsObject') as mock_gso:
            mock_gso.return_value.settings = _make_mock_settings(
                {
                    'footer_link_terms_enabled': True,
                    'footer_page_terms_text': 'Settings active terms',
                }
            )
            pages = view.confirmation_pages
            assert len(pages) == 1
            assert pages[0].text == 'Settings active terms'


def test_get_excluded_system_slugs_error_handling_and_caching(rf):
    """Verify get_excluded_system_slugs handles settings/DB failures and caches on request."""
    from django.db import DatabaseError

    from eventyay.base.models.page import SYSTEM_PAGE_SLUGS, get_excluded_system_slugs

    request = rf.get('/')

    # 1. When settings load fails with DatabaseError, all system pages are excluded as fail-safe
    with patch('eventyay.base.models.page.GlobalSettingsObject') as mock_gso:
        mock_gso.side_effect = DatabaseError('Settings table unreachable')
        excluded = get_excluded_system_slugs()
        assert set(excluded) == SYSTEM_PAGE_SLUGS

    # 2. When DB lookup fails, warning is logged and enabled pages are not falsely excluded
    mock_settings = _make_mock_settings(
        {
            'footer_link_terms_enabled': True,
            'footer_link_privacy_enabled': True,
            'footer_link_support_enabled': True,
        }
    )
    with patch('eventyay.base.models.page.Page.objects.filter', side_effect=DatabaseError('DB down')):
        with patch('eventyay.base.models.page.logger.warning') as mock_log:
            excluded = get_excluded_system_slugs(gs=mock_settings)
            assert mock_log.called
            # None of the enabled pages are excluded due to DB query failure
            assert 'terms' not in excluded

    # 3. Request caching: second call with same request reuses cache
    request._excluded_system_slugs = ['cached_slug']
    assert get_excluded_system_slugs(request=request) == ['cached_slug']
