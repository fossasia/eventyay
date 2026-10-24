import hashlib
import json
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


def public_http_url(value, schemes=('http', 'https')):
    """
    Return ``value`` only when it is an absolute URL using one of ``schemes``, else ``''``.

    Policy URLs end up in ``href`` attributes on every public page. The settings
    form validates them, but values stored before that validation existed (or
    written outside the form) must still never reach visitors as, for example,
    a ``javascript:`` link.
    """
    value = (value or '').strip()
    parts = urlsplit(value)
    if parts.scheme.lower() in schemes and parts.netloc:
        return value
    return ''


def consent_cookie_name(services):
    """
    Name of the cookie Klaro stores consent in, derived from ``services``.

    Klaro remembers consent per service identifier only. Without this, a "yes"
    given to a service would carry over after an administrator changes its
    provider, purpose or category, or reuses a deleted service's identifier.
    Naming the cookie after what the visitor was shown means any such change
    starts every visitor from a fresh cookie with no consent in it.
    """
    identity = sorted([s.name, s.provider, s.purpose, s.category] for s in services)
    digest = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:12]
    return f'eventyay_consent_{digest}'


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

    services = list(published_services(settings))
    config = {
        'elementID': 'klaro',
        'storageMethod': 'cookie',
        'cookieName': consent_cookie_name(services),
        # Klaro links this from the preference modal.
        'privacyPolicy': public_http_url(settings.get('privacy_policy_url')),
        # Opt-in: Klaro reports no consent for optional services until accepted.
        'default': False,
        'mustConsent': False,
        'acceptAll': True,
        'hideDeclineAll': False,
        'purposes': [ConsentCategory.NECESSARY.value] + enabled_consent_categories(settings),
        'services': [service.serialize_public() for service in services],
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
    # An http:// script is blocked on https:// pages, so never emit one.
    return public_http_url(gs.settings.get('privacy_cmp_script_url'), schemes=('https',))


@register.inclusion_tag('eventyay/privacy/embed_placeholder.html')
def consent_embed(service, src, title=''):
    """
    Render a third-party embed behind contextual consent.

    Whenever a consent layer is selected the embed is blocked: the frame URL is
    only emitted as ``data-consent-src``, never as an iframe ``src``, so the
    browser contacts the third party only after consent. The built-in banner
    reveals the frame through ``consent.js``, an external CMP through the
    ``consent-external.js`` bridge. With consent disabled there is nothing to
    gate on, so the frame is rendered directly.

    ``consentable`` says whether the visitor can unblock the embed at all. It is
    false when Klaro does not publish ``service`` (unregistered, disabled, or in
    a category that is switched off) or when the external CMP script is not
    usable, so none is loaded. The embed still stays blocked then, since showing
    it would contact the third party without consent; the placeholder only says
    that the content is unavailable, and the privacy settings warn the
    administrator.
    """
    gs = GlobalSettingsObject()
    provider = gs.settings.get('privacy_consent_provider') or ConsentProvider.DISABLED
    external = provider == ConsentProvider.EXTERNAL
    if external:
        consentable = bool(external_cmp_script())
    elif provider == ConsentProvider.KLARO:
        consentable = published_services(gs.settings).filter(name=service).exists()
    else:
        consentable = False
    return {
        'service': service,
        'src': src,
        'title': title,
        'blocked': provider in (ConsentProvider.KLARO, ConsentProvider.EXTERNAL),
        'consentable': consentable,
        'external': external,
    }
