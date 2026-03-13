"""
Theme models for Eventyay.

Stores design token overrides and theme settings for organizations and events.
"""

import json
import logging
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from eventyay.base.models.base import LoggedModel
from eventyay.base.models.mixins import TimestampedModel

logger = logging.getLogger(__name__)


def validate_token_overrides(value: Dict[str, Any]) -> None:
    """Validate token override structure."""
    if not isinstance(value, dict):
        raise ValidationError(_('Token overrides must be a valid JSON object'))


class BaseTheme(LoggedModel, TimestampedModel, models.Model):
    """
    Base abstract model for theme configuration.

    Stores design token overrides and theme settings.
    """

    class ColorMode(models.TextChoices):
        """Color mode options."""
        LIGHT = 'light', _('Light Mode')
        DARK = 'dark', _('Dark Mode')
        AUTO = 'auto', _('Auto (System Preference)')

    color_mode = models.CharField(
        max_length=10,
        choices=ColorMode.choices,
        default=ColorMode.AUTO,
        verbose_name=_('Color Mode'),
        help_text=_('Default color mode for this theme'),
    )

    token_overrides = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_token_overrides],
        verbose_name=_('Design Token Overrides'),
        help_text=_('JSON object containing token overrides (colors, typography, spacing, etc.)'),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether this theme is currently in use'),
    )

    description = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Description'),
        help_text=_('Internal description of this theme'),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.get_display_name()

    def get_display_name(self) -> str:
        """Get display name for this theme."""
        raise NotImplementedError

    def get_primary_color(self) -> Optional[str]:
        """Extract primary color from overrides."""
        try:
            return self.token_overrides.get('colors', {}).get('primary')
        except (AttributeError, TypeError):
            return None

    def get_secondary_color(self) -> Optional[str]:
        """Extract secondary color from overrides."""
        try:
            return self.token_overrides.get('colors', {}).get('secondary')
        except (AttributeError, TypeError):
            return None

    def clear_overrides(self) -> None:
        """Reset all token overrides."""
        self.token_overrides = {}
        self.save(update_fields=['token_overrides'])

    def update_color(self, color_key: str, hex_value: str) -> None:
        """Update a specific color token."""
        if 'colors' not in self.token_overrides:
            self.token_overrides['colors'] = {}

        self.token_overrides['colors'][color_key] = hex_value
        self.save(update_fields=['token_overrides'])


class OrganizerTheme(BaseTheme):
    """
    Theme configuration for an Organizer.

    Provides organization-wide branding and design token overrides.
    """

    organizer = models.OneToOneField(
        'base.Organizer',
        on_delete=models.CASCADE,
        related_name='theme',
        verbose_name=_('Organizer'),
    )

    logo_url = models.URLField(
        blank=True,
        default='',
        verbose_name=_('Logo URL'),
        help_text=_('URL to organization logo'),
    )

    favicon_url = models.URLField(
        blank=True,
        default='',
        verbose_name=_('Favicon URL'),
        help_text=_('URL to organization favicon'),
    )

    class Meta:
        verbose_name = _('Organizer Theme')
        verbose_name_plural = _('Organizer Themes')
        ordering = ['-created']

    def get_display_name(self) -> str:
        return f'{self.organizer.name} Theme'

    def __str__(self) -> str:
        return f'Theme for {self.organizer.name}'


class EventTheme(BaseTheme):
    """
    Theme configuration for an Event.

    Provides event-specific branding and design token overrides.
    Inherits from organizer theme but can override specific tokens.
    """

    event = models.OneToOneField(
        'base.Event',
        on_delete=models.CASCADE,
        related_name='theme',
        verbose_name=_('Event'),
    )

    inherit_organizer_theme = models.BooleanField(
        default=True,
        verbose_name=_('Inherit Organizer Theme'),
        help_text=_('Whether to inherit token overrides from the organizer theme'),
    )

    custom_css = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Custom CSS'),
        help_text=_('Additional custom CSS rules for this event'),
    )

    class Meta:
        verbose_name = _('Event Theme')
        verbose_name_plural = _('Event Themes')
        ordering = ['-created']

    def get_display_name(self) -> str:
        return f'{self.event.name} Theme'

    def __str__(self) -> str:
        return f'Theme for {self.event.name}'

    def get_effective_tokens(self) -> Dict[str, Any]:
        """
        Get effective tokens for this event.

        Merges organizer and event tokens with proper precedence.
        """
        from eventyay.eventyay_common.theme.loader import ThemeTokenLoader

        organizer_overrides = None
        if self.inherit_organizer_theme and hasattr(self.event.organizer, 'theme'):
            organizer_overrides = self.event.organizer.theme.token_overrides

        return ThemeTokenLoader.get_merged_tokens(
            base_overrides=organizer_overrides,
            event_overrides=self.token_overrides,
        )

    def export_as_json(self) -> str:
        """Export theme configuration as JSON."""
        return json.dumps({
            'name': self.get_display_name(),
            'colorMode': self.color_mode,
            'tokens': self.token_overrides,
            'customCSS': self.custom_css,
        }, indent=2)

    def import_from_json(self, json_data: str) -> None:
        """Import theme configuration from JSON."""
        try:
            data = json.loads(json_data)
            if 'colorMode' in data:
                self.color_mode = data['colorMode']
            if 'tokens' in data:
                self.token_overrides = data['tokens']
            if 'customCSS' in data:
                self.custom_css = data['customCSS']
            self.save()
        except json.JSONDecodeError as e:
            logger.error('Failed to import theme from JSON: %s', e)
            raise ValidationError(_('Invalid JSON format for theme import'))
