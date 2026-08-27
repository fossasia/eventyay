import logging

from django.core.mail import get_connection

from eventyay.base.email import CustomSMTPBackend, SendGridEmail
from eventyay.base.gmail.models import GmailOAuthCredential
from eventyay.base.settings import GlobalSettingsObject
from eventyay.helpers.http import smtp_reachable


logger = logging.getLogger(__name__)


def _build_smtp_backend(*, host, port, username, password, use_tls, use_ssl, timeout):
    return CustomSMTPBackend(
        host=host,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        use_ssl=use_ssl,
        fail_silently=False,
        timeout=timeout,
    )


def get_fallback_mail_backend(*, event=None, timeout=None, exclude_vendor=None):
    gs = GlobalSettingsObject()

    if event is not None and event.settings.smtp_use_custom:
        vendor = event.settings.get('email_vendor')
        if exclude_vendor and vendor == exclude_vendor:
            vendor = None
        if vendor == 'sendgrid' and event.settings.get('send_grid_api_key'):
            return SendGridEmail(api_key=event.settings.send_grid_api_key)
        if vendor == 'smtp' and event.settings.get('smtp_host') and event.settings.get('smtp_port'):
            if smtp_reachable(event.settings.smtp_host, event.settings.smtp_port, timeout=timeout):
                return _build_smtp_backend(
                    host=event.settings.smtp_host,
                    port=event.settings.smtp_port,
                    username=event.settings.smtp_username,
                    password=event.settings.smtp_password,
                    use_tls=event.settings.smtp_use_tls,
                    use_ssl=event.settings.smtp_use_ssl,
                    timeout=timeout,
                )
    elif gs.settings.email_vendor:
        vendor = gs.settings.email_vendor
        if exclude_vendor and vendor == exclude_vendor:
            vendor = None
        if vendor == 'sendgrid' and gs.settings.send_grid_api_key:
            return SendGridEmail(api_key=gs.settings.send_grid_api_key)
        if vendor == 'smtp' and gs.settings.smtp_host and gs.settings.smtp_port:
            if smtp_reachable(gs.settings.smtp_host, gs.settings.smtp_port, timeout=timeout):
                return _build_smtp_backend(
                    host=gs.settings.smtp_host,
                    port=gs.settings.smtp_port,
                    username=gs.settings.smtp_username,
                    password=gs.settings.smtp_password,
                    use_tls=gs.settings.smtp_use_tls,
                    use_ssl=gs.settings.smtp_use_ssl,
                    timeout=timeout,
                )

    return get_connection(fail_silently=False, timeout=timeout)


def get_gmail_mail_backend(*, event=None, timeout=None, force_custom=False):
    from eventyay.base.gmail.backend import GmailAPIEmail

    credential = None
    if event is not None and (event.settings.smtp_use_custom or force_custom):
        if event.settings.get('email_vendor') == 'gmail_api':
            credential = GmailOAuthCredential.get_active_for_event(event)
            if not credential:
                return None
    elif event is None or not event.settings.smtp_use_custom:
        gs = GlobalSettingsObject()
        if gs.settings.get('email_vendor') == 'gmail_api':
            credential = GmailOAuthCredential.get_active_global()
            if not credential:
                return None

    if not credential:
        return None

    fallback = get_fallback_mail_backend(event=event, timeout=timeout, exclude_vendor='gmail_api')
    return GmailAPIEmail(credential=credential, fallback_backend=fallback)
