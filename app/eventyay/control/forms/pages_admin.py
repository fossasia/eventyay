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
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.forms.fields import I18nRichTextFormField

DEFAULT_PAGE_LOCALE = 'en'

# Slugs that expose editable rich-text page content in addition to a footer link.
CONTENT_PAGE_SLUGS = ('terms', 'privacy', 'pricing', 'support')
# Slugs handled by the default-page tab (Documentation is an external link only).
DEFAULT_PAGE_SLUGS = ('terms', 'privacy', 'pricing', 'documentation', 'support')

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
    'startpage_feature_1_title', 'startpage_feature_1_text',
    'startpage_feature_2_title', 'startpage_feature_2_text',
    'startpage_feature_3_title', 'startpage_feature_3_text',
    'startpage_feature_4_title', 'startpage_feature_4_text',
    'footer_page_terms_text',
    'footer_page_privacy_text',
    'footer_page_pricing_text',
    'footer_page_support_text',
)

PAGE_TITLES = {
    'terms': _('Terms'),
    'privacy': _('Privacy'),
    'pricing': _('Pricing'),
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
        self.obj = GlobalSettingsObject()
        self._apply_setting_defaults()
        self._page_locales = self._resolve_page_locales(args, kwargs)
        super().__init__(*args, obj=self.obj, **kwargs)
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
        self.fields['page_locales'] = forms.MultipleChoiceField(
            choices=settings.LANGUAGES,
            required=False,
            widget=forms.MultipleHiddenInput,
        )
        self.initial['page_locales'] = self._page_locales

    def _restrict_locales(self):
        for field in self.fields.values():
            if isinstance(field, I18nFormField):
                field.widget.enabled_locales = self._page_locales

    @property
    def page_locale_choices(self):
        names = dict(settings.LANGUAGES)
        return [(code, str(names.get(code, code))) for code in self._page_locales]

    @property
    def available_locale_choices(self):
        return [
            (code, str(name))
            for code, name in settings.LANGUAGES
            if code not in self._page_locales
        ]

    def save(self):
        self.cleaned_data.pop('locales', None)
        page_locales = self.cleaned_data.get('page_locales') or [DEFAULT_PAGE_LOCALE]
        self.cleaned_data['page_locales'] = page_locales
        super().save()


class StartPageContentForm(PageContentSettingsForm):
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
            sample='The comprehensive platform for all your event needs. Ticketing, Call for Speakers, Scheduling, Check-in, and more.'
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
        help_text=_('e.g. {sample}').format(sample='Create interactive schedules and allow attendees to plan their visit.'),
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
        help_text=_('e.g. {sample}').format(sample='Built on open source technology. Fully customizable and transparent.'),
    )


class FooterContentForm(PageContentSettingsForm):
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
    footer_link_events_url = forms.CharField(required=False, label=_('"Events" link URL'))
    footer_link_terms_enabled = forms.BooleanField(required=False, label=_('Show "Terms" footer link'))
    footer_link_terms_url = forms.CharField(required=False, label=_('"Terms" link URL'))
    footer_link_privacy_enabled = forms.BooleanField(required=False, label=_('Show "Privacy" footer link'))
    footer_link_privacy_url = forms.CharField(required=False, label=_('"Privacy" link URL'))
    footer_link_pricing_enabled = forms.BooleanField(required=False, label=_('Show "Pricing" footer link'))
    footer_link_pricing_url = forms.CharField(required=False, label=_('"Pricing" link URL'))
    footer_link_documentation_enabled = forms.BooleanField(required=False, label=_('Show "Documentation" footer link'))
    footer_link_documentation_url = forms.CharField(required=False, label=_('"Documentation" link URL'))
    footer_link_support_enabled = forms.BooleanField(required=False, label=_('Show "Support" footer link'))
    footer_link_support_url = forms.CharField(required=False, label=_('"Support" link URL'))

    footer_link_groups = (
        ('events', _('Events')),
        ('terms', _('Terms')),
        ('privacy', _('Privacy')),
        ('pricing', _('Pricing')),
        ('documentation', _('Documentation')),
        ('support', _('Support')),
    )

    def _apply_setting_defaults(self):
        for key, value in FOOTER_LINK_DEFAULTS.items():
            if self.obj.settings.get(key) is None:
                self.obj.settings.set(key, value)


class GlobalBannerContentForm(PageContentSettingsForm):
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
        super().__init__(*args, **kwargs)
        self.fields['banner_message'].widget.attrs['rows'] = '2'
        self.fields['banner_message_detail'].widget.attrs['rows'] = '3'


class DefaultPageContentForm(PageContentSettingsForm):
    """Editor for a single default page (Terms, Privacy, Pricing, Support, Documentation)."""

    def __init__(self, *args, slug=None, **kwargs):
        if slug not in DEFAULT_PAGE_SLUGS:
            raise ValueError(f'Unknown default page slug: {slug!r}')
        self.slug = slug
        super().__init__(*args, **kwargs)

    @property
    def page_content_fields(self):
        if self.slug in CONTENT_PAGE_SLUGS:
            return (f'footer_page_{self.slug}_text',)
        return ()

    @property
    def has_content(self):
        return self.slug in CONTENT_PAGE_SLUGS

    def _apply_setting_defaults(self):
        enabled_key = f'footer_link_{self.slug}_enabled'
        url_key = f'footer_link_{self.slug}_url'
        if self.obj.settings.get(enabled_key) is None:
            self.obj.settings.set(enabled_key, FOOTER_LINK_DEFAULTS.get(enabled_key, True))
        if self.obj.settings.get(url_key) is None:
            self.obj.settings.set(url_key, FOOTER_LINK_DEFAULTS.get(url_key, f'/{self.slug}'))

    def _build_dynamic_fields(self):
        slug = self.slug
        enabled_key = f'footer_link_{slug}_enabled'
        url_key = f'footer_link_{slug}_url'
        gs = self.obj.settings

        self.fields[enabled_key] = forms.BooleanField(
            required=False,
            label=_('Show in footer'),
        )
        self.initial[enabled_key] = gs.get(enabled_key, as_type=bool, default=True)

        self.fields[url_key] = forms.CharField(
            required=False,
            label=_('Link URL'),
        )
        self.initial[url_key] = gs.get(url_key, default=FOOTER_LINK_DEFAULTS.get(url_key, f'/{slug}'))

        if self.has_content:
            content_key = f'footer_page_{slug}_text'
            self.fields[content_key] = I18nRichTextFormField(
                required=False,
                label=_('Page content'),
            )
            self.initial[content_key] = gs.get(content_key, as_type=LazyI18nString)
