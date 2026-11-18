def is_valid_provider_config(key, config):
    """Check if a provider configuration dict has the required keys."""
    if not isinstance(config, dict) or not config.get('client_id') or not config.get('secret'):
        return False
    if key == 'openid_connect' and not config.get('server_url'):
        return False
    return True


def order_login_providers(login_providers):
    """
    Return login_providers as a dict with the preferred provider first,
    filtering out any providers that are not fully configured (missing client_id, secret, or server_url).
    """
    if not login_providers:
        return login_providers

    valid_providers = {k: v for k, v in login_providers.items() if is_valid_provider_config(k, v)}

    preferred = get_preferred_provider(valid_providers)
    ordered = {}
    if preferred and preferred in valid_providers and valid_providers[preferred].get('state'):
        ordered[preferred] = valid_providers[preferred]
    for key, value in valid_providers.items():
        if key != preferred:
            ordered[key] = value
    return ordered


def get_preferred_provider(login_providers):
    """Return the provider key that is preferred, or None."""
    if not login_providers:
        return None
    for key, config in login_providers.items():
        if is_valid_provider_config(key, config) and config.get('state') and config.get('is_preferred'):
            return key
    return None
