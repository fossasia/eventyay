import sys
import uuid
from datetime import timedelta

import requests
from django.dispatch import receiver
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString

from pretix import __version__
from pretix.base.models import Event
from pretix.base.plugins import get_all_plugins
from pretix.base.services.mail import mail
from pretix.base.settings import GlobalSettingsObject
from pretix.base.signals import periodic_task
from pretix.celery_app import app
from pretix.helpers.urls import build_absolute_uri

import logging
logger = logging.getLogger(__name__)


@receiver(signal=periodic_task)
def run_update_check(sender, **kwargs):
    gs = GlobalSettingsObject()
    if not gs.settings.update_check_perform:
        return

    if not gs.settings.update_check_last or now() - gs.settings.update_check_last > timedelta(hours=23):
        update_check.apply_async()


@app.task
@scopes_disabled()
def update_check():
    gs = GlobalSettingsObject()

    if not gs.settings.update_check_id:
        gs.settings.set('update_check_id', uuid.uuid4().hex)

    if not gs.settings.update_check_perform:
        return

    if 'runserver' in sys.argv:
        gs.settings.set('update_check_last', now())
        gs.settings.set('update_check_result', {'error': 'development'})
        return

    check_payload = {
        'id': gs.settings.get('update_check_id'),
        'version': __version__,
        'events': {
            'total': Event.objects.count(),
            'live': Event.objects.filter(live=True).count(),
        },
        'plugins': [{'name': p.module, 'version': p.version} for p in get_all_plugins()],
    }
    try:
        r = requests.post('https://eventyay.org/.update_check/', json=check_payload)
        gs.settings.set('update_check_last', now())
        if r.status_code != 200:
            gs.settings.set('update_check_result', {'error': 'http_error'})
        else:
            rdata = r.json()
            update_available = rdata['version']['updatable'] or any(p['updatable'] for p in rdata['plugins'].values())
            gs.settings.set('update_check_result_warning', update_available)
            if update_available and rdata != gs.settings.update_check_result:
                send_update_notification_email()
            gs.settings.set('update_check_result', rdata)
    except requests.RequestException:
        gs.settings.set('update_check_last', now())
        gs.settings.set('update_check_result', {'error': 'unavailable'})

def send_update_notification_email():
    gs = GlobalSettingsObject()
    admin_email = gs.settings.get('update_check_email')
    
    if not admin_email:
        return

    update_result = gs.settings.get('update_check_result')
    if not update_result or 'version' not in update_result:
        return

    latest_version = update_result['version'].get('latest')
    last_notified = gs.settings.get('last_notified_release')
    
    # Only send if new release and we haven't notified about this version yet
    if latest_version and latest_version != last_notified:
        try:
            mail(
                admin_email,
                _('Eventyay update available: v{0}').format(latest_version),
                LazyI18nString.from_gettext(
                    gettext_noop(
                        'A new Eventyay version is available.\n\n'
                        'Current: {current}\n'
                        'Latest: {latest}\n\n'
                        'Release notes:\n'
                        'https://github.com/fossasia/eventyay-tickets/releases/tag/{latest}\n\n'
                        'You received this because this address is configured under:\n'
                        'Admin → Global Settings → Update'
                    )
                ),

                {
                    'current': update_result['version'].get('current'),
                    'latest': latest_version,
                },
            )
            gs.settings.set('last_notified_release', latest_version)
            gs.settings.set('last_notification_sent', now().isoformat())
        except Exception as e:
            logger.error('Failed to send update notification email: %s', e)



def check_result_table():
    gs = GlobalSettingsObject()
    res = gs.settings.update_check_result
    if not res:
        return {'error': 'no_result'}

    if 'error' in res:
        return res

    table = []
    table.append(('pretix', __version__, res['version']['latest'], res['version']['updatable']))
    for p in get_all_plugins():
        if p.module in res['plugins']:
            pdata = res['plugins'][p.module]
            table.append(
                (
                    _('Plugin: %s') % p.name,
                    p.version,
                    pdata['latest'],
                    pdata['updatable'],
                )
            )
        else:
            table.append((_('Plugin: %s') % p.name, p.version, '?', False))

    return table
