from urllib.parse import urlsplit

from django import template
from django.utils.html import json_script
from django.utils.translation import gettext

from eventyay.base.models.privacy import (
    ConsentCategory,
    ConsentProvider,
    enabled_consent_categories,
    published_services,
)
from eventyay.base.settings import GlobalSettingsObject


register = template.Library()

CONFIG_ELEMENT_ID = 'klaro-config'


def public_http_url(value):
    """
    Return ``value`` only when it is an absolute http(s) URL, else ``''``.

    Policy URLs end up in ``href`` attributes on every public page. The settings
    form validates them, but values stored before that validation existed (or
    written outside the form) must still never reach visitors as, for example,
    a ``javascript:`` link.
    """
    value = (value or '').strip()
    parts = urlsplit(value)
    if parts.scheme.lower() in ('http', 'https') and parts.netloc:
        return value
    return ''


def build_consent_config():
    """
    Build the Klaro configuration from admin settings and the service registry.

    Returns ``None`` when the built-in banner is not the active provider, so
    templates can skip rendering the consent layer entirely.
    """
    gs = GlobalSettingsObject()
    settings = gs.settings
    provider = settings.get('privacy_consent_provider') or ConsentProvider.DISABLED

    if provider != ConsentProvider.KLARO:
        return None

    config = {
        'elementID': 'klaro',
        'storageMethod': 'cookie',
        'cookieName': 'eventyay_consent',
        # Klaro links this from the preference modal.
        'privacyPolicy': public_http_url(settings.get('privacy_policy_url')),
        # Opt-in: Klaro reports no consent for optional services until accepted.
        'default': False,
        'mustConsent': False,
        'acceptAll': True,
        'hideDeclineAll': False,
        'purposes': [ConsentCategory.NECESSARY.value] + enabled_consent_categories(settings),
        'services': [service.serialize_public() for service in published_services(settings)],
    }

    # Klaro has no cookie policy option, so consent.js adds this link to the
    # notice and the preference modal itself. Klaro ignores keys it does not know.
    cookie_policy_url = public_http_url(settings.get('privacy_cookie_policy_url'))
    if cookie_policy_url:
        config['eventyayCookiePolicy'] = {'url': cookie_policy_url, 'label': gettext('Cookie Policy')}

    return config


@register.simple_tag
def consent_config():
    """
    Render the Klaro configuration as a JSON ``<script>`` element.

    Service titles and purposes are administrator-supplied, so the payload is
    written with ``json_script``: it escapes ``<``, ``>`` and ``&`` as unicode
    escapes, which keeps a value containing ``</script>`` from closing the
    element early and injecting markup into every public page.
    """
    config = build_consent_config()
    if config is None:
        return None
    return json_script(config, CONFIG_ELEMENT_ID)


@register.simple_tag
def consent_provider():
    """consent_provider method."""
    gs = GlobalSettingsObject()
    return gs.settings.get('privacy_consent_provider') or ConsentProvider.DISABLED


@register.simple_tag
def cookie_policy_url():
    """The Cookie Policy URL, if it is safe to link to from a public page."""
    gs = GlobalSettingsObject()
    return public_http_url(gs.settings.get('privacy_cookie_policy_url'))


@register.simple_tag
def external_cmp_script():
    """external_cmp_script method."""
    gs = GlobalSettingsObject()
    if (gs.settings.get('privacy_consent_provider') or '') != ConsentProvider.EXTERNAL:
        return ''
    return gs.settings.get('privacy_cmp_script_url') or ''


@register.inclusion_tag('eventyay/privacy/embed_placeholder.html')
def consent_embed(service, src, title=''):
    """
    Render a third-party embed behind contextual consent.

    A placeholder is only emitted when the visitor can actually unblock it: the
    built-in banner must be active, and ``service`` must be published in the
    Klaro configuration. consent.js swaps the placeholder in once
    ``getConsent(service)`` is true, which never happens for a service Klaro
    does not know about (unregistered, disabled, or in a category that is
    switched off).

    In every other case the embed is rendered directly. With consent disabled
    there is nothing to gate on, and an external CMP does its own blocking of
    third-party frames. Emitting a placeholder there would leave the content
    permanently unreachable.
    """
    gs = GlobalSettingsObject()
    provider = gs.settings.get('privacy_consent_provider') or ConsentProvider.DISABLED
    blocked = (
        provider == ConsentProvider.KLARO
        and published_services(gs.settings).filter(name=service).exists()
    )
    return {
        'service': service,
        'src': src,
        'title': title,
        'blocked': blocked,
    }
