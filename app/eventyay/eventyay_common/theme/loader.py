"""
Theme token management utilities for Eventyay.

This module provides core functionality for design token loading, merging,
validation, and CSS variable export.
"""

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class ThemeTokenLoader:
    """Load and manage design tokens for theming."""

    BASE_TOKENS_PATH = Path(__file__).parent / 'default_tokens.json'
    OVERRIDES_SCHEMA_PATH = Path(__file__).parent / 'overrides_schema.json'

    @classmethod
    def load_base_tokens(cls) -> dict[str, Any]:
        """Load base/foundation tokens from default theme."""
        try:
            with open(cls.BASE_TOKENS_PATH) as f:
                data = json.load(f)
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error('Failed to load base tokens: %s', e)
            return {}

    @classmethod
    def load_overrides_schema(cls) -> dict[str, Any]:
        """Load validation schema for user overrides."""
        try:
            with open(cls.OVERRIDES_SCHEMA_PATH) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error('Failed to load overrides schema: %s', e)
            return {}

    @classmethod
    def validate_token_path_value(cls, token_path: str, value: Any) -> None:
        """
        Validate a single token path and value against the overrides schema.

        Reconstructs the nested structure for the path and validates it against
        the schema to enforce type constraints on known token paths while
        allowing schema-defined additional properties.
        """
        import jsonschema

        schema = cls.load_overrides_schema()
        if not schema:
            return

        keys = [k for k in token_path.split('.') if k]
        if not keys:
            raise ValueError('Invalid token path')

        payload: dict[str, Any] = {}
        curr = payload
        for k in keys[:-1]:
            curr[k] = {}
            curr = curr[k]
        curr[keys[-1]] = value

        jsonschema.validate(instance=payload, schema=schema)

    @classmethod
    def resolve_token_references(
        cls, tokens: dict[str, Any], base_tokens: dict[str, Any] | None = None
    ) -> dict[str, Any]:
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
    def _flatten_dict(d: dict, parent_key: str = '') -> dict[str, Any]:
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
    def _get_nested_value(d: dict, path: str) -> Any | None:
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
    def _set_nested_value(d: dict, path: str, value: Any) -> None:
        """Set nested value using dot notation."""
        keys = path.split('.')
        current = d
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    @classmethod
    def merge_tokens(cls, base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
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
    def _deep_merge(base: dict, overrides: dict) -> None:
        """Recursively merge overrides into base."""
        for key, value in overrides.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ThemeTokenLoader._deep_merge(base[key], value)
            else:
                base[key] = deepcopy(value)

    @classmethod
    def export_css_variables(cls, tokens: dict[str, Any], prefix: str = '--') -> str:
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
                if path.startswith('colors.'):
                    norm_var = f'{prefix}color-{path[7:].replace(".", "-")}'
                    if norm_var != var_name:
                        css_lines.append(f'  {norm_var}: {value};')

        css_lines.append('}')
        return '\n'.join(css_lines)

    @classmethod
    def get_merged_tokens(
        cls,
        base_overrides: dict[str, Any] | None = None,
        event_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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

        return cls.resolve_token_references(base_tokens, base_tokens=base_tokens)
