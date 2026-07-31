import logging
from typing import Any

from celery import Task
from django_scopes import scopes_disabled

from ..base.models import Event
from .utils import EventCreatedFor

logger = logging.getLogger(__name__)


class SendEventTask(Task):
    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> Any:
        """
        Handle successful task completion by updating event settings.
        Set the event settings to "create_for" both:
        indicate that the event is created for both tickets and talk

        Args:
            retval: Task return value
            task_id: ID of the completed task
            args: Original task arguments
            kwargs: Original task keyword arguments

        Returns:
            Any: Result from parent class on_success method
        """
        event_slug = kwargs.get('event', {}).get('slug', '')
        try:
            with scopes_disabled():
                event = Event.objects.get(slug=event_slug)
                event.settings.set('create_for', EventCreatedFor.BOTH.value)
                event.save()
        except Event.DoesNotExist:
            logger.error('Event with slug %s does not exist', event_slug)
        return super().on_success(retval, task_id, args, kwargs)
