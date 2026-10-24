"""Forms backing the consolidated admin *Pages* area.

Every tab (Start page, Footer, Global banner and the default pages) stores its
content on the :class:`GlobalSettingsObject`.  The i18n content fields are
restricted to the configured page languages so the interface shows a single
language at a time (paired with a compact language switcher) instead of
rendering every locale vertically.
"""

import json

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextarea, I18nTextInput
from i18nfield.strings import LazyI18nString

from eventyay.base.forms import SettingsForm
from eventyay.base.models.page import validate_footer_url
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.forms.fields import I18nRichTextFormField


DEFAULT_PAGE_LOCALE = 'en'

# Slugs that expose editable rich-text page content in addition to a footer link.
CONTENT_PAGE_SLUGS = ('terms', 'privacy', 'support')
# Slugs handled by the default-page tab (Documentation is an external link only).
DEFAULT_PAGE_SLUGS = ('terms', 'privacy', 'documentation', 'support')

# Every i18n settings key that stores per-locale page content across all tabs.
# Used by the locale-remove endpoint to wipe content for a dropped locale globally.
ALL_PAGE_I18N_KEYS = (
    'footer_text',
    'footer_link',
    'banner_message',
    'banner_message_detail',
    'startpage_header_text',
    'startpage_hero_title',
    'startpage_hero_text',
    'startpage_feature_1_title',
    'startpage_feature_1_text',
    'startpage_feature_2_title',
    'startpage_feature_2_text',
    'startpage_feature_3_title',
    'startpage_feature_3_text',
    'startpage_feature_4_title',
    'startpage_feature_4_text',
    'footer_page_terms_text',
    'footer_page_privacy_text',
    'footer_page_support_text',
)

PAGE_TITLES = {
    'terms': _('Terms'),
    'privacy': _('Privacy'),
    'documentation': _('Documentation'),
    'support': _('Support'),
}

FOOTER_LINK_DEFAULTS = {
    'footer_link_events_enabled': True,
    'footer_link_events_url': '/upcoming',
    'footer_link_terms_enabled': True,
    'footer_link_terms_url': '/terms',
    'footer_link_privacy_enabled': True,
    'footer_link_privacy_url': '/privacy',
    'footer_link_pricing_enabled': True,
    'footer_link_pricing_url': '/pricing',
    'footer_link_documentation_enabled': True,
    'footer_link_documentation_url': 'https://docs.eventyay.com',
    'footer_link_support_enabled': True,
    'footer_link_support_url': '/support',
}


class PageContentSettingsForm(SettingsForm):
    """Base form for the admin *Pages* tabs.

    Subclasses declare their fields as usual.  Any i18n field is limited to the
    configured page languages, and a hidden ``page_locales`` field keeps the set
    of active languages in sync with the compact language switcher.
    """

    auto_fields = []
    # i18n setting keys scanned to auto-enable locales that already have content.
    page_content_fields = ()

    def __init__(self, *args, **kwargs):
        """Initialize the settings form and configure active page locales."""
        self.obj = kwargs.pop('obj', None) or GlobalSettingsObject()
        self._page_locales = self._resolve_page_locales(args, kwargs)
        super().__init__(*args, obj=self.obj, **kwargs)
        self._apply_setting_defaults()
        self._build_dynamic_fields()
        self._add_page_locales_field()
        self._restrict_locales()

    # -- hooks -----------------------------------------------------------------

    def _apply_setting_defaults(self):
        """Persist default values for unset settings (overridden by subclasses)."""

    def _build_dynamic_fields(self):
        """Add fields that depend on runtime state (overridden by subclasses)."""

    # -- locale handling -------------------------------------------------------

    def _resolve_page_locales(self, args, kwargs):
        """Resolve the list of active language codes from settings, content, and submitted form data."""
        valid = {code for code, _name in settings.LANGUAGES}
        raw = self.obj.settings.get('page_locales')
        if isinstance(raw, str):
            try:
                locales = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                locales = [DEFAULT_PAGE_LOCALE]
        elif isinstance(raw, (list, tuple)):
            locales = list(raw)
        else:
            locales = [DEFAULT_PAGE_LOCALE]
        locales = [code for code in locales if code in valid] or [DEFAULT_PAGE_LOCALE]

        for key in self.page_content_fields:
            for lang, text in self._locale_dict(self.obj.settings.get(key)).items():
                if text and lang in valid and lang not in locales:
                    locales.append(lang)

        for lang in self._submitted_locales(args, kwargs):
            if lang in valid and lang not in locales:
                locales.append(lang)
        return locales

    @staticmethod
    def _locale_dict(raw):
        """Extract a mapping of language code to content string from raw i18n data."""
        if isinstance(raw, LazyI18nString):
            raw = raw.data
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return {}
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _submitted_locales(args, kwargs):
        """Extract submitted language codes from form input data."""
        data = kwargs.get('data')
        if data is None and args:
            data = args[0]
        if data is None:
            return []
        if hasattr(data, 'getlist'):
            return [str(v).strip() for v in data.getlist('page_locales') if str(v).strip()]
        value = data.get('page_locales')
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if str(v).strip()]
        return [str(value).strip()] if value else []

    def _add_page_locales_field(self):
        """Attach the hidden multiple-choice field tracking active page locales."""
        self.fields['page_locales'] = forms.MultipleChoiceField(
            choices=settings.LANGUAGES,
            required=False,
            widget=forms.MultipleHiddenInput,
        )
        self.initial['page_locales'] = self._page_locales

    def _restrict_locales(self):
        """Restrict i18n form field widgets to the active page locales."""
        for field in self.fields.values():
            if isinstance(field, I18nFormField):
                field.widget.enabled_locales = self._page_locales

    @property
    def page_locale_choices(self):
        """Return choices of currently active page locales for template display."""
        names = dict(settings.LANGUAGES)
        return [(code, str(names.get(code, code))) for code in self._page_locales]

    @property
    def available_locale_choices(self):
        """Return language choices that are not yet active for the page."""
        return [(code, str(name)) for code, name in settings.LANGUAGES if code not in self._page_locales]

    def save(self):
        """Save form fields and persist updated page locales to settings."""
        self.cleaned_data.pop('locales', None)
        page_locales = self.cleaned_data.get('page_locales') or [DEFAULT_PAGE_LOCALE]
        self.cleaned_data['page_locales'] = page_locales
        super().save()


class StartPageContentForm(PageContentSettingsForm):
    """Editor for start page header, hero, and feature box settings."""

    auto_fields = ['startpage_header_image']
    page_content_fields = (
        'startpage_header_text',
        'startpage_hero_title',
        'startpage_hero_text',
        'startpage_feature_1_title',
        'startpage_feature_1_text',
        'startpage_feature_2_title',
        'startpage_feature_2_text',
        'startpage_feature_3_title',
        'startpage_feature_3_text',
        'startpage_feature_4_title',
        'startpage_feature_4_text',
    )

    startpage_header_text = I18nRichTextFormField(
        required=False,
        label=_('Start page header text'),
        help_text=_('e.g. {sample}').format(sample='Welcome to our event platform!'),
    )

    startpage_show_hero = forms.BooleanField(
        required=False,
        label=_('Show hero section'),
        help_text=_('Enable the hero section at the top of the start page.'),
    )
    startpage_hero_title = I18nFormField(
        required=False,
        label=_('Hero title'),
        widget=I18nTextInput,
        help_text=_('e.g. {sample}').format(sample='Eventyay – Open Source Event Management Platform'),
    )
    startpage_hero_text = I18nFormField(
        required=False,
        label=_('Hero text'),
        widget=I18nTextarea,
        help_text=_('e.g. {sample}').format(
            sample=(
                'The comprehensive platform for all your event needs. '
                'Ticketing, Call for Speakers, Scheduling, Check-in, and more.'
            )
        ),
    )

    startpage_show_features = forms.BooleanField(
        required=False,
        label=_('Show feature boxes'),
        help_text=_('Enable the feature boxes section on the start page.'),
    )
    startpage_feature_1_title = I18nFormField(
        required=False,
        label=_('Feature 1 title'),
        widget=I18nTextInput,
        help_text=_('e.g. {sample}').format(sample='Ticketing'),
    )
    startpage_feature_1_text = I18nFormField(
        required=False,
        label=_('Feature 1 text'),
        widget=I18nTextarea,
        help_text=_('e.g. {sample}').format(sample='Sell tickets, manage orders, and handle check-ins effortlessly.'),
    )
    startpage_feature_2_title = I18nFormField(
        required=False,
        label=_('Feature 2 title'),
        widget=I18nTextInput,
        help_text=_('e.g. {sample}').format(sample='Call for Speakers'),
    )
    startpage_feature_2_text = I18nFormField(
        required=False,
        label=_('Feature 2 text'),
        widget=I18nTextarea,
        help_text=_('e.g. {sample}').format(sample='Accept submissions, review proposals, and build your schedule.'),
    )
    startpage_feature_3_title = I18nFormField(
        required=False,
        label=_('Feature 3 title'),
        widget=I18nTextInput,
        help_text=_('e.g. {sample}').format(sample='Schedules'),
    )
    startpage_feature_3_text = I18nFormField(
        required=False,
        label=_('Feature 3 text'),
        widget=I18nTextarea,
        help_text=_('e.g. {sample}').format(
            sample='Create interactive schedules and allow attendees to plan their visit.'
        ),
    )
    startpage_feature_4_title = I18nFormField(
        required=False,
        label=_('Feature 4 title'),
        widget=I18nTextInput,
        help_text=_('e.g. {sample}').format(sample='Open Source'),
    )
    startpage_feature_4_text = I18nFormField(
        required=False,
        label=_('Feature 4 text'),
        widget=I18nTextarea,
        help_text=_('e.g. {sample}').format(
            sample='Built on open source technology. Fully customizable and transparent.'
        ),
    )


class FooterContentForm(PageContentSettingsForm):
    """Editor for footer settings, including additional text, link, and core footer links."""

    page_content_fields = ('footer_text', 'footer_link')

    footer_text = I18nFormField(
        widget=I18nTextInput,
        required=False,
        label=_('Additional footer text'),
        help_text=_('Will be included as additional text in the footer, site-wide.'),
    )
    footer_link = I18nFormField(
        widget=I18nTextInput,
        required=False,
        label=_('Additional footer link'),
        help_text=_('Will be included as the link in the additional footer text.'),
    )

    footer_link_events_enabled = forms.BooleanField(required=False, label=_('Show "Events" footer link'))
    footer_link_events_url = forms.CharField(
        required=False, label=_('"Events" link URL'), validators=[validate_footer_url]
    )
    footer_link_terms_enabled = forms.BooleanField(required=False, label=_('Show "Terms" footer link'))
    footer_link_terms_url = forms.CharField(
        required=False, label=_('"Terms" link URL'), validators=[validate_footer_url]
    )
    footer_link_privacy_enabled = forms.BooleanField(required=False, label=_('Show "Privacy" footer link'))
    footer_link_privacy_url = forms.CharField(
        required=False, label=_('"Privacy" link URL'), validators=[validate_footer_url]
    )
    footer_link_pricing_enabled = forms.BooleanField(required=False, label=_('Show "Pricing" footer link'))
    footer_link_pricing_url = forms.CharField(
        required=False, label=_('"Pricing" link URL'), validators=[validate_footer_url]
    )
    footer_link_documentation_enabled = forms.BooleanField(required=False, label=_('Show "Documentation" footer link'))
    footer_link_documentation_url = forms.CharField(
        required=False, label=_('"Documentation" link URL'), validators=[validate_footer_url]
    )
    footer_link_support_enabled = forms.BooleanField(required=False, label=_('Show "Support" footer link'))
    footer_link_support_url = forms.CharField(
        required=False, label=_('"Support" link URL'), validators=[validate_footer_url]
    )

    footer_link_groups = (
        ('events', _('Events')),
        ('terms', _('Terms')),
        ('privacy', _('Privacy')),
        ('pricing', _('Pricing')),
        ('documentation', _('Documentation')),
        ('support', _('Support')),
    )

    def _apply_setting_defaults(self):
        """Populate default values for unset footer link settings into initial data without persisting."""
        for key, value in FOOTER_LINK_DEFAULTS.items():
            if self.obj.settings.get(key) is None:
                self.initial.setdefault(key, value)

    def clean(self):
        """Validate footer URLs and additional footer link against malformed syntax."""
        cleaned_data = super().clean()
        for key, _label in self.footer_link_groups:
            field_name = f'footer_link_{key}_url'
            url_val = cleaned_data.get(field_name)
            if url_val:
                try:
                    validate_footer_url(url_val)
                except forms.ValidationError as e:
                    self.add_error(field_name, e)

        footer_link = cleaned_data.get('footer_link')
        if footer_link:
            if isinstance(footer_link, LazyI18nString):
                links = footer_link.data if isinstance(footer_link.data, dict) else {'': str(footer_link)}
            elif isinstance(footer_link, dict):
                links = footer_link
            else:
                links = {'': str(footer_link)}
            for val in links.values():
                if val:
                    try:
                        validate_footer_url(val)
                    except forms.ValidationError as e:
                        self.add_error('footer_link', e)
                        break
        return cleaned_data


class GlobalBannerContentForm(PageContentSettingsForm):
    """Editor for the sitewide global alert message banner."""

    page_content_fields = ('banner_message', 'banner_message_detail')

    banner_message_enabled = forms.BooleanField(
        required=False,
        label=_('Show global message banner'),
        help_text=_('When enabled, the banner is displayed on platform pages.'),
    )
    banner_message = I18nRichTextFormField(
        required=False,
        label=_('Short banner text'),
    )
    banner_message_detail = I18nRichTextFormField(
        required=False,
        label=_('Detail text'),
    )

    def __init__(self, *args, **kwargs):
        """Configure widget row heights for banner messages."""
        super().__init__(*args, **kwargs)
        self.fields['banner_message'].widget.attrs['rows'] = '2'
        self.fields['banner_message_detail'].widget.attrs['rows'] = '3'


class DefaultPageContentForm(PageContentSettingsForm):
    """Editor for a single default page (Terms, Privacy, Support, Documentation)."""

    def __init__(self, *args, slug=None, **kwargs):
        """Initialize default page form for the specified slug."""
        if slug not in DEFAULT_PAGE_SLUGS:
            raise ValueError(f'Unknown default page slug: {slug!r}')
        self.slug = slug
        super().__init__(*args, **kwargs)

    @property
    def page_content_fields(self):
        """Return settings keys holding i18n content for this page."""
        if self.slug in CONTENT_PAGE_SLUGS:
            return (f'footer_page_{self.slug}_text',)
        return ()

    @property
    def has_content(self):
        """Return True if this default page slug manages editable text content."""
        return self.slug in CONTENT_PAGE_SLUGS

    def _apply_setting_defaults(self):
        """Populate default enabled and URL settings into initial data without persisting."""
        enabled_key = f'footer_link_{self.slug}_enabled'
        url_key = f'footer_link_{self.slug}_url'
        if self.obj.settings.get(enabled_key) is None:
            self.initial.setdefault(enabled_key, FOOTER_LINK_DEFAULTS.get(enabled_key, True))
        if self.obj.settings.get(url_key) is None:
            self.initial.setdefault(url_key, FOOTER_LINK_DEFAULTS.get(url_key, f'/{self.slug}'))

    def _build_dynamic_fields(self):
        """Construct form fields for the default page."""
        slug = self.slug
        enabled_key = f'footer_link_{slug}_enabled'
        url_key = f'footer_link_{slug}_url'
        gs = self.obj.settings

        help_text = (
            _(
                'When disabled, or when pointing to a built-in page with no configured content, '
                'this link is hidden from the footer and the page returns a 404 Not Found error.'
            )
            if self.has_content
            else _('When disabled, this link is hidden from the footer.')
        )
        label = _('Active / Enable page') if self.has_content else _('Show in footer')
        self.fields[enabled_key] = forms.BooleanField(
            required=False,
            label=label,
            help_text=help_text,
        )

        self.initial[enabled_key] = gs.get(enabled_key, as_type=bool, default=True)

        self.fields[url_key] = forms.CharField(
            required=False,
            label=_('Link URL'),
            validators=[validate_footer_url],
        )
        self.initial[url_key] = gs.get(url_key, default=FOOTER_LINK_DEFAULTS.get(url_key, f'/{slug}'))

        if self.has_content:
            content_key = f'footer_page_{slug}_text'
            self.fields[content_key] = I18nRichTextFormField(
                required=False,
                label=_('Page content'),
            )
            self.initial[content_key] = gs.get(content_key, as_type=LazyI18nString)

    def clean(self):
        """Validate dynamic page footer URL against malformed syntax."""
        cleaned_data = super().clean()
        url_key = f'footer_link_{self.slug}_url'
        url_val = cleaned_data.get(url_key)
        if url_val:
            try:
                validate_footer_url(url_val)
            except forms.ValidationError as e:
                self.add_error(url_key, e)
        return cleaned_data
