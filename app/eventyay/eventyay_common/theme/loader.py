"""
Theme token management utilities for Eventyay.

This module provides core functionality for design token loading, merging,
validation, and CSS variable export.
"""

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ThemeTokenLoader:
    """Load and manage design tokens for theming."""

    BASE_TOKENS_PATH = Path(__file__).parent / 'default_tokens.json'

    @classmethod
    def load_base_tokens(cls) -> Dict[str, Any]:
        """Load base/foundation tokens from default theme."""
        try:
            with open(cls.BASE_TOKENS_PATH, 'r') as f:
                data = json.load(f)
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error('Failed to load base tokens: %s', e)
            return {}

    @classmethod
    def resolve_token_references(cls, tokens: Dict[str, Any], base_tokens: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resolve token references (e.g., {colors.primary}) in semantic tokens.

        :param tokens: Token dictionary potentially containing references
        :param base_tokens: Base tokens for resolving references
        :return: Resolved tokens with all references replaced
        """
        if base_tokens is None:
            base_tokens = cls.load_base_tokens()

        resolved = deepcopy(tokens)
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            has_unresolved = False

            for key, value in cls._flatten_dict(resolved).items():
                if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                    has_unresolved = True
                    ref_path = value[1:-1]
                    resolved_value = cls._get_nested_value(base_tokens, ref_path)
                    if resolved_value is not None:
                        cls._set_nested_value(resolved, key, resolved_value)

            if not has_unresolved:
                break

        return resolved

    @staticmethod
    def _flatten_dict(d: Dict, parent_key: str = '') -> Dict[str, Any]:
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f'{parent_key}.{k}' if parent_key else k
            if isinstance(v, dict):
                items.extend(ThemeTokenLoader._flatten_dict(v, new_key).items())
            else:
                items.append((new_key, v))
        return dict(items)

    @staticmethod
    def _get_nested_value(d: Dict, path: str) -> Optional[Any]:
        """Get nested value using dot notation."""
        keys = path.split('.')
        current = d
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    @staticmethod
    def _set_nested_value(d: Dict, path: str, value: Any) -> None:
        """Set nested value using dot notation."""
        keys = path.split('.')
        current = d
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    @classmethod
    def merge_tokens(cls, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge override tokens into base tokens.

        :param base: Base token set
        :param overrides: Override tokens (highest priority)
        :return: Merged token dictionary
        """
        result = deepcopy(base)
        cls._deep_merge(result, overrides)
        return result

    @staticmethod
    def _deep_merge(base: Dict, overrides: Dict) -> None:
        """Recursively merge overrides into base."""
        for key, value in overrides.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ThemeTokenLoader._deep_merge(base[key], value)
            else:
                base[key] = deepcopy(value)

    @classmethod
    def export_css_variables(cls, tokens: Dict[str, Any], prefix: str = '--') -> str:
        """
        Export tokens as CSS variables.

        :param tokens: Resolved tokens dictionary
        :param prefix: CSS variable prefix (e.g., '--')
        :return: CSS string with variables
        """
        css_lines = [':root {']
        flattened = cls._flatten_dict(tokens)

        for path, value in sorted(flattened.items()):
            if isinstance(value, (str, int, float)):
                var_name = f'{prefix}{path.replace(".", "-")}'
                css_lines.append(f'  {var_name}: {value};')

        css_lines.append('}')
        return '\n'.join(css_lines)

    @classmethod
    def get_merged_tokens(
        cls,
        base_overrides: Optional[Dict[str, Any]] = None,
        event_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get fully merged tokens with proper precedence.

        Precedence: base tokens < org overrides < event overrides

        :param base_overrides: Organization-level token overrides
        :param event_overrides: Event-level token overrides
        :return: Fully merged tokens
        """
        base_tokens = cls.load_base_tokens()

        if base_overrides:
            base_tokens = cls.merge_tokens(base_tokens, base_overrides)

        if event_overrides:
            base_tokens = cls.merge_tokens(base_tokens, event_overrides)

        return cls.resolve_token_references(base_tokens)
