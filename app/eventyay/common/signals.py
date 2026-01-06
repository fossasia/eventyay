import logging
import uuid
from functools import wraps
from typing import Any, Callable

import django.dispatch
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.dispatch import receiver
from django.dispatch.dispatcher import NO_RECEIVERS
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event
from eventyay.base.signals import resolve_app_for_module, check_plugin_active

logger = logging.getLogger(__name__)


class EventPluginSignal(django.dispatch.Signal):
    """An extension to Django's built-in signals.

    It sends out it's events only to receivers which belong to plugins
    that are enabled for the given Event.
    """

    def get_live_receivers(self, sender):
        receivers = self._live_receivers(sender)
        if not receivers:
            return []
        return receivers[0]

    def _is_active(self, sender, receiver):
        # Find the Django application this belongs to
        module_path = receiver.__module__
        is_core_module = any(module_path.startswith(cm) for cm in settings.CORE_MODULES)
        
        # Resolve the app using thread-safe cached function
        app = resolve_app_for_module(module_path)
        
        return check_plugin_active(sender, app, is_core_module, settings.EVENTYAY_PLUGINS_EXCLUDE, lambda s: s.plugin_list)

    def send(self, sender: Event, **named) -> list[tuple[Callable, Any]]:
        """Send signal from sender to all connected receivers that belong to
        plugins enabled for the given Event.

        sender is required to be an instance of
        ``pretalx.event.models.Event``.
        """
        if sender and not isinstance(sender, Event):
            raise ValueError('Sender needs to be an event.')

        responses = []
        if not self.receivers or self.sender_receivers_cache.get(sender) is NO_RECEIVERS:
            return responses

        for receiver in self.get_live_receivers(sender):
            if self._is_active(sender, receiver):
                response = receiver(signal=self, sender=sender, **named)
                responses.append((receiver, response))
        return sorted(
            responses,
            key=lambda response: (response[0].__module__, response[0].__name__),
        )

    def send_robust(self, sender: Event, **named) -> list[tuple[Callable, Any]]:
        """Send signal from sender to all connected receivers that belong to
        plugins enabled for the given Event. If a receiver raises an Exception,
        it is returned as the response instead of propagating.

        sender is required to be an instance of
        ``pretalx.event.models.Event``.
        """
        if sender and not isinstance(sender, Event):
            raise ValueError('Sender needs to be an event.')

        responses = []
        if not self.receivers or self.sender_receivers_cache.get(sender) is NO_RECEIVERS:
            return []

        for receiver in self.get_live_receivers(sender):
            if self._is_active(sender, receiver):
                try:
                    response = receiver(signal=self, sender=sender, **named)
                except Exception as err:
                    responses.append((receiver, err))
                else:
                    responses.append((receiver, response))
        return sorted(
            responses,
            key=lambda response: (response[0].__module__, response[0].__name__),
        )

    def send_chained(self, sender: Event, chain_kwarg_name, **named) -> list[tuple[Callable, Any]]:
        """Send signal from sender to all connected receivers. The return value
        of the first receiver will be used as the keyword argument specified by
        ``chain_kwarg_name`` in the input to the second receiver and so on. The
        return value of the last receiver is returned by this method.

        sender is required to be an instance of
        ``pretalx.event.models.Event``.
        """
        if sender and not isinstance(sender, Event):
            raise ValueError('Sender needs to be an event.')

        response = named.get(chain_kwarg_name)
        if not self.receivers or self.sender_receivers_cache.get(sender) is NO_RECEIVERS:  # pragma: no cover
            return response

        for receiver in self.get_live_receivers(sender):
            if self._is_active(sender, receiver):
                named[chain_kwarg_name] = response
                response = receiver(signal=self, sender=sender, **named)
        return response


def minimum_interval(minutes_after_success, minutes_after_error=0, minutes_running_timeout=30):
    """
    Use this decorator on receivers of the ``periodic_task`` signal to ensure the receiver
    function has at least ``minutes_after_success`` minutes between two successful runs and
    at least ``minutes_after_error`` minutes between two failed runs.
    You also get a simple locking mechanism making sure the function is not called a second
    time while it is running, unless ``minutes_running_timeout`` have passed. This locking
    is naive and should not be completely relied upon.
    """

    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key_running = f'pretalx_periodic_{func.__module__}.{func.__name__}_running'
            key_result = f'pretalx_periodic_{func.__module__}.{func.__name__}_result'

            if cache.get(key_running) or cache.get(key_result):
                return

            uniqid = str(uuid.uuid4())
            cache.set(key_running, uniqid, timeout=minutes_running_timeout * 60)
            try:
                retval = func(*args, **kwargs)
            except Exception as e:
                try:
                    cache.set(key_result, 'error', timeout=minutes_after_error * 60)
                except Exception:
                    logger.exception('Could not store result')
                raise e
            else:
                try:
                    cache.set(key_result, 'success', timeout=minutes_after_success * 60)
                except Exception:
                    logger.exception('Could not store result')
                return retval
            finally:
                try:
                    if cache.get(key_running) == uniqid:
                        cache.delete(key_running)
                except Exception:
                    logger.exception('Could not release lock')

        return wrapper

    return decorate


periodic_task = django.dispatch.Signal()
"""
This is a regular django signal (no pretalx event signal) that we send out every
time the periodic task cronjob runs. This interval is not sharply defined, it can
be everything between a minute and a day. The actions you perform should be
idempotent, meaning it should not make a difference if this is sent out more often
than expected.
"""

register_data_exporters = EventPluginSignal()

register_my_data_exporters = EventPluginSignal()
"""
This signal is sent out to get all known data exporters. Receivers should return a
subclass of pretalx.common.exporter.BaseExporter

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""
activitylog_display = EventPluginSignal()
"""
To display an instance of the ``ActivityLog`` model to a human user,
``pretalx.common.signals.activitylog_display`` will be sent out with an ``activitylog``
argument.

The first received response that is not ``None`` will be used to display the log entry
to the user. The receivers are expected to return plain (lazy) text.

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""
activitylog_object_link = EventPluginSignal()
"""
To display the relationship of an instance of the ``ActivityLog`` model to another model
to a human user, ``pretalx.common.signals.activitylog_object_link`` will be sent out
with an ``activitylog`` argument.

The first received response that is not ``None`` will be used to display the related object
to the user. The receivers are expected to return an HTML link as a string.
Make sure that any user content in the HTML code you return is properly escaped!

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

auth_html = django.dispatch.Signal()
"""
Responses to the ``pretalx.common.signals.auth_html`` signal will be displayed as
additional content on any sign-up or login page, for example a login link to your
custom authentication method (see :ref:`plugin-auth`).

As with all event-plugin signals, the ``sender`` keyword argument will contain the event
if an event-specific login view is used (for the generic ``/orga/`` login page, the
``sender`` is ``None``).

Additionally, the signal is passed the ``request`` keyword argument, and an optional
``next_url`` keyword argument. If ``next_url`` is not empty, you should direct the
user to the given link once they have completed the authentication.
"""

profile_bottom_html = django.dispatch.Signal()
"""
To display additional HTML content on the user profile/settings pages.
"""

register_locales = django.dispatch.Signal()
"""
To provide additional languages via plugins, you will have to provide some settings in
the pretalx settings file, and return a list of the registered locales as response
to this plugin signal. Every entry should be a tuple of two strings, the first being
the locale code, the second being the display name of the locale. (Though pretalx will
also accept just a locale code.)

You should always return your locale when no ``sender`` keyword argument is given to
make your locale available to the makemessages command. Otherwise, check that your
plugin is enabled in the current event context if your locale should be scoped to
events with your plugin activated.
"""


@receiver(periodic_task)
@scopes_disabled()
def process_scheduled_emails(sender, **kwargs):
    """
    Process scheduled emails that are due for sending.
    Handles both QueuedMail (Talk/CfP) and EmailQueue (Tickets).
    
    Uses select_for_update(skip_locked=True) to prevent duplicate sends
    when multiple workers process the same emails concurrently.
    """
    from eventyay.base.models.mail import QueuedMail
    from eventyay.plugins.sendmail.models import EmailQueue

    # Process QueuedMail (Talk/CfP component)
    with transaction.atomic():
        due_queued_mails = QueuedMail.objects.filter(
            scheduled_at__lte=now(),
            sent__isnull=True,
        ).select_for_update(skip_locked=True)

        for mail in due_queued_mails:
            try:
                mail.send()
                logger.info(
                    "[ScheduledMail] QueuedMail ID %s sent successfully.",
                    mail.pk
                )
            except Exception:
                logger.exception(
                    "[ScheduledMail] Failed to send QueuedMail ID %s",
                    mail.pk
                )

    # Process EmailQueue (Tickets component)
    with transaction.atomic():
        due_email_queues = EmailQueue.objects.filter(
            scheduled_at__lte=now(),
            sent_at__isnull=True,
        ).select_for_update(skip_locked=True)

        for mail in due_email_queues:
            try:
                mail.send()
                logger.info(
                    "[ScheduledMail] EmailQueue ID %s sent successfully.",
                    mail.pk
                )
            except Exception:
                logger.exception(
                    "[ScheduledMail] Failed to send EmailQueue ID %s",
                    mail.pk
                )
