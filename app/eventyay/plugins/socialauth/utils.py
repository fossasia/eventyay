"""
Utility functions for login provider management.

This module centralizes login provider validation and manipulation logic
to ensure consistency across the codebase and prevent logic divergence.
"""
import logging
from typing import Optional

from pydantic import ValidationError

from .schemas.login_providers import LoginProviders

logger = logging.getLogger(__name__)


def validate_login_providers(raw_providers: Optional[dict]) -> LoginProviders:
    """
    Validate and parse login provider configuration.

    This function ensures that the LoginProviders schema invariants are enforced,
    including the single-preferred-provider constraint. All provider configuration
    should pass through this function before use.

    Args:
        raw_providers: Raw provider configuration dict, can be None
   
    Returns:
        LoginProviders: Validated provider configuration with invariants enforced,
                       or default configuration if invalid
    """
    if raw_providers is None:
        return LoginProviders()

    try:
        return LoginProviders.model_validate(raw_providers)
    except ValidationError as e:
        # Sanitize error messages to avoid logging sensitive data
        sanitized_errors = []
        for error in e.errors():
            sanitized_error = {key: value for key, value in error.items() if key != 'input'}
            sanitized_errors.append(sanitized_error)
        logger.warning(
            "Invalid login provider configuration: %d validation error(s). "
            "Falling back to defaults. Details (sanitized): %s",
            e.error_count(),
            sanitized_errors
        )
        return LoginProviders()


def set_preferred_provider(
    providers: LoginProviders, 
    provider_name: str
) -> LoginProviders:
    """
    Set a specific provider as the preferred login method.

    This centralizes the logic for managing the preferred provider to prevent
    divergence between different parts of the codebase. The schema validator
    ensures only one enabled provider can be preferred.

    Logic:
    - Clears is_preferred flag from all providers
    - Sets is_preferred=True only if the provider name is valid and the provider is enabled
    - The schema validator (ensure_single_preferred) enforces the final invariant

    Args:
        providers: Current LoginProviders instance
        provider_name: Name of provider to set as preferred (must be enabled)
   
    Returns:
        Updated LoginProviders instance with new preferred provider and
        schema invariants enforced
   
    Note:
        If provider_name is empty, invalid, or the provider is disabled,
        all providers will have is_preferred=False after validation.
    """
    # Convert to mutable dict
    providers_dict = providers.model_dump()

    # Reset all is_preferred flags
    for name in LoginProviders.model_fields.keys():
        if name in providers_dict:
            providers_dict[name]['is_preferred'] = False
 
    # Set the selected provider as preferred (only if enabled and valid)
    if (provider_name 
        and provider_name in LoginProviders.model_fields.keys() 
        and provider_name in providers_dict
        and providers_dict[provider_name].get('state', False)):
        providers_dict[provider_name]['is_preferred'] = True

    # Validate and return - this ensures schema invariants are enforced
    # The validator will handle any edge cases (e.g., disabled preferred providers)
    return LoginProviders.model_validate(providers_dict)
