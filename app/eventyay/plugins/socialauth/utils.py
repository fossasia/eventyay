import logging
from pydantic import ValidationError
from .schemas.login_providers import LoginProviders

logger = logging.getLogger(__name__)


def validate_login_providers(raw_providers: dict | None) -> LoginProviders:
    """
    Validate and parse login provider configuration.
    
    Args:
        raw_providers: Raw provider configuration dict, can be None
        
    Returns:
        LoginProviders: Validated provider configuration, or default if invalid
    """
    if raw_providers is None:
        return LoginProviders()
    
    try:
        return LoginProviders.model_validate(raw_providers)
    except ValidationError as e:
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
