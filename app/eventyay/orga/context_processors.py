import logging
from urllib.parse import urljoin

from django.conf import settings
from django.utils.module_loading import import_string

from eventyay.common.text.phrases import CALL_FOR_SPEAKER_LOGIN_BTN_LABELS
from eventyay.orga.signals import html_head, nav_event, nav_event_settings, nav_global

SessionStore = import_string(f'{settings.SESSION_ENGINE}.SessionStore')
logger = logging.getLogger(__name__)


def collect_signal(signal, kwargs):
    result = []
    for _, response in signal.send_robust(**kwargs):
        if isinstance(response, list):
            result += [r for r in response if not isinstance(r, Exception)]
        elif not isinstance(response, Exception):
            result.append(response)
    return result


def orga_events(request):
    """Add data to all template contexts."""
    context = {'settings': settings}

    # Extract site specific values from individual settings attributes and add them to the context
    # so that templates can use simple context variables instead of accessing the settings object
    # directly.
    context['site_name'] = settings.INSTANCE_NAME
    context['base_path'] = settings.BASE_PATH
    context['common_path'] = urljoin(settings.BASE_PATH, '/common')
    context['tickets_common'] = context['common_path']
    context['tickets_path'] = urljoin(settings.BASE_PATH, '/control')
    context['talks_path'] = urljoin(settings.BASE_PATH, '/orga/event')
    context['admin_path'] = urljoin(settings.BASE_PATH, '/admin')
    # Login button label
    key = settings.CALL_FOR_SPEAKER_LOGIN_BUTTON_LABEL
    button_label = CALL_FOR_SPEAKER_LOGIN_BTN_LABELS.get(key)
    if not button_label:
        logger.warning('%s does not exist in CALL_FOR_SPEAKER_LOGIN_BTN_LABELS', key)
        button_label = CALL_FOR_SPEAKER_LOGIN_BTN_LABELS['default']
    context['login_button_label'] = button_label

    if not request.path_info.startswith('/orga/'):
        return {
            'login_button_label': button_label,
        }

    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return context

    context['staff_session'] = request.user.has_active_staff_session(request.session.session_key)

    if not getattr(request, 'event', None):
        context['nav_global'] = [
            entry for entry in collect_signal(nav_global, {'sender': None, 'request': request}) if entry
        ]
        return context

    _nav_event = []
    for _, response in nav_event.send_robust(request.event, request=request):
        _nav_event += response if (response and isinstance(response, list)) else []

    context['nav_event'] = _nav_event
    context['nav_settings'] = collect_signal(nav_event_settings, {'sender': request.event, 'request': request})
    context['html_head'] = ''.join(collect_signal(html_head, {'sender': request.event, 'request': request}))

    if (
        not request.event.is_public
        and request.event.custom_domain
        and request.user.has_perm('base.view_event', request.event)
    ):
        child_session_key = f'child_session_{request.event.pk}'
        child_session = request.session.get(child_session_key)
        store = SessionStore()
        if not child_session or not store.exists(child_session):
            store[f'eventyay_event_access_{request.event.pk}'] = request.session.session_key
            store.create()
            context['new_session'] = store.session_key
            request.session[child_session_key] = store.session_key
            request.session['event_access'] = True
        else:
            context['new_session'] = child_session
            request.session['event_access'] = True

    return context
