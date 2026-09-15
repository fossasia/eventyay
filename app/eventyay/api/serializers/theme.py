"""
Serializers for theme API endpoints.

Provides serialization logic for theme configuration and token management.
"""

from rest_framework import serializers

from eventyay.eventyay_common.models import EventTheme, OrganizerTheme
from eventyay.eventyay_common.theme.loader import ThemeTokenLoader


class BaseThemeSerializer(serializers.ModelSerializer):
    """Base serializer for theme models."""

    primary_color = serializers.SerializerMethodField()
    secondary_color = serializers.SerializerMethodField()
    tokens = serializers.SerializerMethodField()

    class Meta:
        fields = [
            'id',
            'color_mode',
            'token_overrides',
            'is_active',
            'description',
            'primary_color',
            'secondary_color',
            'tokens',
            'created',
            'updated',
        ]
        read_only_fields = ['id', 'created', 'updated']

    def get_primary_color(self, obj) -> str | None:
        """Extract primary color from theme."""
        return obj.get_primary_color()

    def get_secondary_color(self, obj) -> str | None:
        """Extract secondary color from theme."""
        return obj.get_secondary_color()

    def get_tokens(self, obj) -> dict:
        """Get merged tokens for the theme."""
        try:
            if isinstance(obj, EventTheme):
                return obj.get_effective_tokens()
            return ThemeTokenLoader.get_merged_tokens(base_overrides=obj.token_overrides)
        except Exception:
            return {}
    
    def to_representation(self, instance):
        """Override to ensure color_mode uses camelCase in response."""
        data = super().to_representation(instance)
        # Convert snake_case to camelCase for API consistency
        if 'color_mode' in data:
            data['colorMode'] = data.pop('color_mode')
        if 'token_overrides' in data:
            data['tokenOverrides'] = data.pop('token_overrides')
        if 'primary_color' in data:
            data['primaryColor'] = data.pop('primary_color')
        if 'secondary_color' in data:
            data['secondaryColor'] = data.pop('secondary_color')
        if 'is_active' in data:
            data['isActive'] = data.pop('is_active')
        return data


class OrganizerThemeSerializer(BaseThemeSerializer):
    """Serializer for OrganizerTheme model."""

    organizer_name = serializers.CharField(source='organizer.name', read_only=True)
    organizer_slug = serializers.CharField(source='organizer.slug', read_only=True)

    class Meta(BaseThemeSerializer.Meta):
        model = OrganizerTheme
        fields = BaseThemeSerializer.Meta.fields + [
            'logo_url',
            'favicon_url',
            'organizer_name',
            'organizer_slug',
        ]


class EventThemeSerializer(BaseThemeSerializer):
    """Serializer for EventTheme model."""

    event_name = serializers.CharField(source='event.name', read_only=True)
    event_slug = serializers.CharField(source='event.slug', read_only=True)
    organizer_slug = serializers.CharField(source='event.organizer.slug', read_only=True)

    class Meta(BaseThemeSerializer.Meta):
        model = EventTheme
        fields = BaseThemeSerializer.Meta.fields + [
            'inherit_organizer_theme',
            'custom_css',
            'event_name',
            'event_slug',
            'organizer_slug',
        ]


class ThemeTokenUpdateSerializer(serializers.Serializer):
    """Serializer for updating individual theme tokens."""

    token_path = serializers.CharField(max_length=255, required=True)
    value = serializers.JSONField(required=True)
    color_mode = serializers.ChoiceField(
        choices=['light', 'dark', 'auto'],
        required=False,
    )

    class Meta:
        fields = ['token_path', 'value', 'color_mode']


class ThemeExportSerializer(serializers.Serializer):
    """Serializer for exporting/importing theme configuration."""

    name = serializers.CharField(max_length=255, required=False)
    colorMode = serializers.ChoiceField(choices=['light', 'dark', 'auto'])
    tokens = serializers.JSONField()
    customCSS = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        fields = ['name', 'colorMode', 'tokens', 'customCSS']


class ThemePreviewSerializer(serializers.Serializer):
    """Serializer for theme preview data."""

    tokens = serializers.JSONField()
    isDark = serializers.BooleanField()
    colorMode = serializers.ChoiceField(choices=['light', 'dark', 'auto'])
    primaryColor = serializers.CharField()
    secondaryColor = serializers.CharField()

    class Meta:
        fields = ['tokens', 'isDark', 'colorMode', 'primaryColor', 'secondaryColor']
