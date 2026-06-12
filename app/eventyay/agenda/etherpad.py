"""Public session-page integration for Etherpad collaborative notes.

Renders a small "Collaborative Notes" block below a session's public page when
the event has Etherpad enabled, the session has a pad URL, and the organiser has
chosen to show it publicly. The pad content itself is hosted on the configured
Etherpad instance, not inside eventyay.
"""

from django.dispatch import receiver
from django.template.loader import render_to_string

from eventyay.agenda.signals import html_below_session_pages
from eventyay.base.settings import GlobalSettingsObject


def is_etherpad_publicly_visible(event, submission):
    """Whether the pad link may be shown to anonymous public visitors."""
    if not submission or not submission.etherpad_url:
        return False
    if not GlobalSettingsObject().settings.etherpad_enabled:
        return False
    if not event.get_feature_flag('etherpad_enabled'):
        return False
    return bool((event.display_settings or {}).get('etherpad_public'))


@receiver(html_below_session_pages, dispatch_uid='agenda_etherpad_session_link')
def add_etherpad_link(sender, request, submission, **kwargs):
    if not is_etherpad_publicly_visible(sender, submission):
        return ''
    return render_to_string(
        'agenda/etherpad_session_block.html',
        {'etherpad_url': submission.etherpad_url},
        request=request,
    )
