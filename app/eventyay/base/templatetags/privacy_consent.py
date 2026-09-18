from urllib.parse import urlsplit

from django import template
from django.utils.html import json_script

from eventyay.base.models.privacy import (
    ConsentCategory,
    ConsentProvider,
    ThirdPartyService,
    enabled_consent_categories,
)
from eventyay.base.settings import GlobalSettingsObject


register = template.Library()

CONFIG_ELEMENT_ID = 'klaro-config'


def _url_with_scheme(value, schemes):
    """
    Return ``value`` only if it uses one of ``schemes``, otherwise ``''``.

    The settings form already validates these URLs, but values stored before
    that validation existed, or written from the shell, never pass through it.
    """
    value = (value or '').strip()
    return value if urlsplit(value).scheme.lower() in schemes else ''


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

    enabled = enabled_consent_categories(settings)
    services = ThirdPartyService.objects.filter(enabled=True)

    return {
        'elementID': 'klaro',
        'storageMethod': 'cookie',
        'cookieName': 'eventyay_consent',
        'privacyPolicy': _url_with_scheme(settings.get('privacy_policy_url'), ('http', 'https')),
        'cookiePolicy': _url_with_scheme(settings.get('privacy_cookie_policy_url'), ('http', 'https')),
        # Opt-in: nothing optional runs until the visitor accepts it.
        'default': False,
        'mustConsent': False,
        'acceptAll': True,
        'hideDeclineAll': False,
        'purposes': [ConsentCategory.NECESSARY.value] + enabled,
        'services': [
            service.serialize_public() for service in services if service.required or service.category in enabled
        ],
    }


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
def external_cmp_script():
    """external_cmp_script method."""
    gs = GlobalSettingsObject()
    if (gs.settings.get('privacy_consent_provider') or '') != ConsentProvider.EXTERNAL:
        return ''
    # An http:// script is blocked on https:// pages, so never emit one.
    return _url_with_scheme(gs.settings.get('privacy_cmp_script_url'), ('https',))


@register.inclusion_tag('eventyay/privacy/embed_placeholder.html')
def consent_embed(service, src, title=''):
    """
    Render a third-party embed behind contextual consent.

    Whenever a consent layer is active the frame URL is only emitted as
    ``data-consent-src``, never as an iframe ``src``, so the browser contacts
    the third party only after consent. An external CMP loads asynchronously
    and cannot reliably stop a frame that is already navigating. The built-in
    banner reveals the frame through ``consent.js``, an external CMP through
    the ``consent-external.js`` bridge. With consent disabled there is nothing
    to gate on, so the frame is rendered directly.
    """
    gs = GlobalSettingsObject()
    provider = gs.settings.get('privacy_consent_provider') or ConsentProvider.DISABLED
    return {
        'service': service,
        'src': src,
        'title': title,
        'blocked': provider in (ConsentProvider.KLARO, ConsentProvider.EXTERNAL),
        'external': provider == ConsentProvider.EXTERNAL,
    }
