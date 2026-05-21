"""
Experience resolver service for hybrid attendee experience.

Computes an ExperienceProfile for a given OrderPosition based on its
participation_mode (with optional per-position override). No Django request
object is required, making this safe to call from Celery tasks, exporters,
and management commands.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from eventyay.base.models.choices import ParticipationMode

logger = logging.getLogger(__name__)


@dataclass
class ExperienceProfile:
    """
    Resolved set of behavioural attributes for a specific attendee.

    Fields with defaults must come after fields without defaults.
    Adding new optional fields with defaults is backward-compatible.
    """

    participation_mode: str
    has_stream_access: bool
    show_join_online_nav: bool
    primary_cta_url: Optional[str] = None
    calendar_location: Optional[str] = None


class ExperienceResolver:
    """
    Computes an ExperienceProfile for a given OrderPosition.

    No Django request object is required.

    To add a new participation mode (e.g. 'interpreter'):
      1. Add the value to ParticipationMode in eventyay.base.models.choices.
      2. Add an entry to _HANDLERS mapping the value to a builder method name.
      3. Implement the builder method following the _build_*_profile pattern.
    """

    # Registry: participation_mode value → builder method name
    _HANDLERS: dict[str, str] = {
        ParticipationMode.VIRTUAL: '_build_virtual_profile',
        ParticipationMode.IN_PERSON: '_build_in_person_profile',
    }

    def resolve(self, position, event=None) -> ExperienceProfile:
        """
        Resolve an ExperienceProfile for the given OrderPosition.

        :param position: An OrderPosition instance (must have product accessible).
        :param event: Optional Event instance; used for URL building and location.
        :raises ValueError: If position has no associated Product, or if the
                            resolved participation_mode is unknown.
        """
        if position.product_id is None:
            raise ValueError(
                f'OrderPosition {position.pk} has no associated Product; '
                'cannot resolve experience profile.'
            )

        mode = position.participation_mode_override or position.product.participation_mode
        handler_name = self._HANDLERS.get(mode)
        if handler_name is None:
            raise ValueError(
                f'Unknown participation_mode "{mode}" on OrderPosition {position.pk}. '
                'Register a handler in ExperienceResolver._HANDLERS.'
            )
        return getattr(self, handler_name)(position, event)

    # ------------------------------------------------------------------
    # Profile builders
    # ------------------------------------------------------------------

    def _build_virtual_profile(self, position, event) -> ExperienceProfile:
        stream_url = self._get_stream_url(position, event)
        return ExperienceProfile(
            participation_mode=ParticipationMode.VIRTUAL,
            has_stream_access=True,
            show_join_online_nav=True,
            primary_cta_url=stream_url,
            calendar_location=stream_url or self._get_event_url(position, event),
        )

    def _build_in_person_profile(self, position, event) -> ExperienceProfile:
        location = str(event.location) if event and event.location else None
        return ExperienceProfile(
            participation_mode=ParticipationMode.IN_PERSON,
            has_stream_access=False,
            show_join_online_nav=False,
            primary_cta_url=None,
            calendar_location=location,
        )

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def _get_stream_url(self, position, event) -> Optional[str]:
        """
        Return the online-video join URL for the event, or None if not configured.
        Uses the presale:event.onlinevideo.join named URL.
        """
        if event is None:
            return None
        try:
            from eventyay.multidomain.urlreverse import build_absolute_uri

            return build_absolute_uri(event, 'presale:event.onlinevideo.join')
        except Exception:
            logger.warning(
                'Could not build stream URL for event %s',
                getattr(event, 'slug', event),
                exc_info=True,
            )
            return None

    def _get_event_url(self, position, event) -> Optional[str]:
        """Return the event index URL, or None if it cannot be resolved."""
        if event is None:
            return None
        try:
            from eventyay.multidomain.urlreverse import build_absolute_uri

            return build_absolute_uri(event, 'presale:event.index')
        except Exception:
            logger.warning(
                'Could not build event URL for event %s',
                getattr(event, 'slug', event),
                exc_info=True,
            )
            return None
