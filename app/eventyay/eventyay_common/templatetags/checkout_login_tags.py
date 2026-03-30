from django import template
from django.conf import settings

from eventyay.base.auth import get_auth_backends
from eventyay.base.settings import GlobalSettingsObject
from eventyay.eventyay_common.views.auth import (
    _get_preferred_provider,
    _order_login_providers,
)

register = template.Library()


@register.inclusion_tag('eventyay_common/auth/_checkout_login_modal_inner.html', takes_context=True)
def checkout_login_modal_body(context):
    """
    Build checkout login modal content using the same OAuth provider config and ordering
    as eventyay_common.views.auth.login (global login_providers + preferred provider).
    """
    request = context.get('request')
    gs = GlobalSettingsObject()
    raw_providers = gs.settings.get('login_providers', as_type=dict) or {}
    ordered = _order_login_providers(raw_providers)
    enabled_providers = [
        (key, cfg)
        for key, cfg in ordered.items()
        if isinstance(cfg, dict) and cfg.get('state')
    ]
    preferred_provider = _get_preferred_provider(raw_providers)
    if preferred_provider and not any(k == preferred_provider for k, _ in enabled_providers):
        preferred_provider = None

    backenddict = get_auth_backends()
    native = backenddict.get('native')
    show_native_login = bool(native and native.visible)

    return {
        'request': request,
        'enabled_providers': enabled_providers,
        'preferred_provider': preferred_provider,
        'can_reset': settings.EVENTYAY_PASSWORD_RESET,
        'can_register': settings.EVENTYAY_REGISTRATION,
        'show_native_login': show_native_login,
        'has_oauth_providers': bool(enabled_providers),
    }
