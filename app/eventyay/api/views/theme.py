"""
API views for theme management.

Provides endpoints for retrieving, updating, and managing theme configurations.
"""

import logging
from typing import Any

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from eventyay.api.serializers.theme import (
    EventThemeSerializer,
    OrganizerThemeSerializer,
    ThemeExportSerializer,
    ThemePreviewSerializer,
    ThemeTokenUpdateSerializer,
)
from eventyay.base.models import Event, Organizer
from eventyay.eventyay_common.models import EventTheme, OrganizerTheme
from eventyay.eventyay_common.theme.loader import ThemeTokenLoader

logger = logging.getLogger(__name__)


class OrganizerThemeViewSet(viewsets.ViewSet):
    """
    ViewSet for managing organization-level themes.

    Provides endpoints for retrieving, updating, and customizing themes
    at the organization scope.
    """
    permission_classes = [AllowAny]

    def get_organizer(self, request: Request, organizer_slug: str) -> Organizer:
        """Get organizer or raise 404."""
        return get_object_or_404(Organizer, slug=organizer_slug)

    def get_theme(self, organizer: Organizer) -> OrganizerTheme:
        """Get or create organizer theme."""
        theme, _ = OrganizerTheme.objects.get_or_create(organizer=organizer)
        return theme

    @staticmethod
    def _organizer_slug_from_kwargs(kwargs: dict[str, Any]) -> str | None:
        return kwargs.get('organizer_slug') or kwargs.get('organizer')

    @staticmethod
    def _can_change_organizer(request: Request, organizer: Organizer) -> bool:
        return request.user.has_organizer_permission(
            organizer,
            'can_change_organizer_settings',
            request=request,
        )

    @staticmethod
    def _set_nested_override(overrides: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
        keys = path.split('.')
        if not keys:
            return overrides
        current = overrides
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        return overrides

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Retrieve organizer theme configuration."""
        organizer_slug = self._organizer_slug_from_kwargs(kwargs)
        organizer = self.get_organizer(request, organizer_slug)
        theme = self.get_theme(organizer)
        serializer = OrganizerThemeSerializer(theme)
        return Response(serializer.data)

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Retrieve organizer theme configuration (list route)."""
        organizer_slug = self._organizer_slug_from_kwargs(kwargs)
        organizer = self.get_organizer(request, organizer_slug)
        theme = self.get_theme(organizer)
        serializer = OrganizerThemeSerializer(theme)
        return Response(serializer.data)

    def update(self, request: Request, *args, **kwargs) -> Response:
        """Update organizer theme configuration."""
        organizer_slug = self._organizer_slug_from_kwargs(kwargs)
        organizer = self.get_organizer(request, organizer_slug)
        theme = self.get_theme(organizer)

        # Check permissions
        if not self._can_change_organizer(request, organizer):
            return Response(
                {'detail': 'You do not have permission to update this theme.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = OrganizerThemeSerializer(theme, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='update-token')
    def update_token(self, request: Request, *args, **kwargs) -> Response:
        """Update a specific theme token."""
        organizer_slug = self._organizer_slug_from_kwargs(kwargs)
        organizer = self.get_organizer(request, organizer_slug)
        theme = self.get_theme(organizer)

        if not self._can_change_organizer(request, organizer):
            return Response(
                {'detail': 'You do not have permission to update this theme.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ThemeTokenUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                path = serializer.validated_data['token_path']
                value = serializer.validated_data['value']
                overrides = dict(theme.token_overrides or {})
                theme.token_overrides = self._set_nested_override(overrides, path, value)
                if 'color_mode' in serializer.validated_data:
                    theme.color_mode = serializer.validated_data['color_mode']
                theme.save(update_fields=['token_overrides', 'color_mode', 'updated'])

                return Response(
                    {'success': True, 'message': 'Token updated successfully.'},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                logger.error('Failed to update token: %s', e)
                return Response(
                    {'detail': 'Failed to update token.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='export')
    def export(self, request: Request, *args, **kwargs) -> Response:
        """Export theme configuration as JSON."""
        organizer_slug = self._organizer_slug_from_kwargs(kwargs)
        organizer = self.get_organizer(request, organizer_slug)
        theme = self.get_theme(organizer)

        return Response({
            'tokens': theme.token_overrides,
            'colorMode': theme.color_mode,
            'description': theme.description,
        })

    @action(detail=False, methods=['post'], url_path='import')
    def import_theme(self, request: Request, *args, **kwargs) -> Response:
        """Import theme configuration from JSON."""
        organizer_slug = self._organizer_slug_from_kwargs(kwargs)
        organizer = self.get_organizer(request, organizer_slug)
        theme = self.get_theme(organizer)

        if not self._can_change_organizer(request, organizer):
            return Response(
                {'detail': 'You do not have permission to update this theme.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ThemeExportSerializer(data=request.data)
        if serializer.is_valid():
            theme.token_overrides = serializer.validated_data.get('tokens', {})
            theme.color_mode = serializer.validated_data.get('colorMode', 'auto')
            theme.save()

            return Response(
                {'success': True, 'message': 'Theme imported successfully.'},
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EventThemeViewSet(viewsets.ViewSet):
    """
    ViewSet for managing event-level themes.

    Provides endpoints for retrieving, updating, and customizing themes
    at the event scope. Event themes can override organizer themes.
    """

    permission_classes = [AllowAny]  # Allow anonymous access to read themes

    @staticmethod
    def _slugs_from_kwargs(kwargs: dict[str, Any]) -> tuple[str | None, str | None]:
        organizer_slug = kwargs.get('organizer_slug') or kwargs.get('organizer')
        event_slug = kwargs.get('event_slug') or kwargs.get('event')
        return organizer_slug, event_slug

    def get_event(self, organizer_slug: str, event_slug: str) -> Event:
        """Get event or raise 404."""
        organizer = get_object_or_404(Organizer, slug=organizer_slug)
        return get_object_or_404(Event, slug=event_slug, organizer=organizer)

    def get_theme(self, event: Event) -> EventTheme:
        """Get or create event theme."""
        theme, _ = EventTheme.objects.get_or_create(event=event)
        return theme

    @staticmethod
    def _can_change_event(request: Request, event: Event) -> bool:
        return request.user.has_event_permission(
            event.organizer,
            event,
            'can_change_event_settings',
            request=request,
        )

    @staticmethod
    def _set_nested_override(overrides: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
        keys = path.split('.')
        if not keys:
            return overrides
        current = overrides
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        return overrides

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Retrieve event theme configuration."""
        organizer_slug, event_slug = self._slugs_from_kwargs(kwargs)
        event = self.get_event(organizer_slug, event_slug)
        theme = self.get_theme(event)
        serializer = EventThemeSerializer(theme)
        return Response(serializer.data)

    def retrieve(self, request: Request, pk: str = None, *args, **kwargs) -> Response:
        """Retrieve event theme configuration."""
        organizer_slug, event_slug = self._slugs_from_kwargs(kwargs)
        event = self.get_event(organizer_slug, event_slug)
        theme = self.get_theme(event)
        serializer = EventThemeSerializer(theme)
        return Response(serializer.data)

    def update(self, request: Request, *args, **kwargs) -> Response:
        """Update event theme configuration."""
        organizer_slug, event_slug = self._slugs_from_kwargs(kwargs)
        event = self.get_event(organizer_slug, event_slug)
        theme = self.get_theme(event)

        if not self._can_change_event(request, event):
            return Response(
                {'detail': 'You do not have permission to update this theme.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = EventThemeSerializer(theme, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='preview')
    def preview(self, request: Request, *args, **kwargs) -> Response:
        """Get theme preview data for live preview."""
        organizer_slug, event_slug = self._slugs_from_kwargs(kwargs)
        event = self.get_event(organizer_slug, event_slug)
        theme = self.get_theme(event)

        tokens = theme.get_effective_tokens()
        primary = theme.get_primary_color() or tokens.get('colors', {}).get('primary', '#EB2188')
        secondary = theme.get_secondary_color() or tokens.get('colors', {}).get('secondary', '#3B82F6')

        return Response({
            'tokens': tokens,
            'isDark': theme.color_mode == 'dark',
            'colorMode': theme.color_mode,
            'primaryColor': primary,
            'secondaryColor': secondary,
        })

    @action(detail=False, methods=['post'], url_path='update-token')
    def update_token(self, request: Request, *args, **kwargs) -> Response:
        """Update a specific event theme token."""
        organizer_slug, event_slug = self._slugs_from_kwargs(kwargs)
        event = self.get_event(organizer_slug, event_slug)
        theme = self.get_theme(event)

        if not self._can_change_event(request, event):
            return Response(
                {'detail': 'You do not have permission to update this theme.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ThemeTokenUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                path = serializer.validated_data['token_path']
                value = serializer.validated_data['value']
                overrides = dict(theme.token_overrides or {})
                theme.token_overrides = self._set_nested_override(overrides, path, value)
                if 'color_mode' in serializer.validated_data:
                    theme.color_mode = serializer.validated_data['color_mode']
                theme.save(update_fields=['token_overrides', 'color_mode', 'updated'])

                return Response(
                    {'success': True, 'message': 'Token updated successfully.'},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                logger.error('Failed to update event token: %s', e)
                return Response(
                    {'detail': 'Failed to update token.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='reset')
    def reset(self, request: Request, *args, **kwargs) -> Response:
        """Reset event theme to base tokens."""
        organizer_slug, event_slug = self._slugs_from_kwargs(kwargs)
        event = self.get_event(organizer_slug, event_slug)
        theme = self.get_theme(event)

        if not self._can_change_event(request, event):
            return Response(
                {'detail': 'You do not have permission to update this theme.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        theme.clear_overrides()
        return Response(
            {'success': True, 'message': 'Theme reset to defaults.'},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'], url_path='export')
    def export(self, request: Request, *args, **kwargs) -> Response:
        """Export event theme configuration as JSON."""
        organizer_slug, event_slug = self._slugs_from_kwargs(kwargs)
        event = self.get_event(organizer_slug, event_slug)
        theme = self.get_theme(event)

        return Response({
            'name': theme.get_display_name(),
            'tokens': theme.token_overrides,
            'colorMode': theme.color_mode,
            'customCSS': theme.custom_css,
        })

    @action(detail=False, methods=['post'], url_path='import')
    def import_theme(self, request: Request, *args, **kwargs) -> Response:
        """Import event theme configuration from JSON."""
        organizer_slug, event_slug = self._slugs_from_kwargs(kwargs)
        event = self.get_event(organizer_slug, event_slug)
        theme = self.get_theme(event)

        if not self._can_change_event(request, event):
            return Response(
                {'detail': 'You do not have permission to update this theme.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            theme.import_from_json(request.data.get('json', '{}'))
            return Response(
                {'success': True, 'message': 'Theme imported successfully.'},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error('Failed to import event theme: %s', e)
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
