import logging
from contextlib import suppress
from email.utils import formataddr
from smtplib import SMTPResponseException, SMTPSenderRefused

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.smtp import EmailBackend

from eventyay.base.models import Event
from eventyay.celery_app import app
from eventyay.common.exceptions import SendMailException

logger = logging.getLogger(__name__)


class CustomSMTPBackend(EmailBackend):
    def test(self, from_addr):
        try:  # pragma: no cover
            self.open()
            self.connection.ehlo_or_helo_if_needed()
            (code, resp) = self.connection.mail(from_addr, [])
            if code != 250:
                logger.warning(f'Error testing mail settings, code {code}, resp: {resp}')
                raise SMTPSenderRefused(code, resp, sender=from_addr)
            (code, resp) = self.connection.rcpt('testdummy@pretalx.com')
            if code not in (250, 251):
                logger.warning(f'Error testing mail settings, code {code}, resp: {resp}')
                raise SMTPSenderRefused(code, resp, sender=from_addr)
        finally:
            self.close()


class TolerantDict(dict):
    def __missing__(self, key):
        """Don't fail when formatting strings with a dict with missing keys."""
        return key


DEBUG_DOMAINS = [
    'localhost',
    'example.org',
    'example.com',
]


@app.task(bind=True, name='pretalx.common.send_mail')
def mail_send_task(
    self,
    to: list,
    subject: str,
    body: str,
    html: str,
    reply_to: list = None,
    event: int = None,
    cc: list = None,
    bcc: list = None,
    headers: dict = None,
    attachments: list = None,
):
    if isinstance(to, str):
        to = [to]
    to = [addr for addr in to if addr]

    if not settings.DEBUG and settings.EMAIL_BACKEND != 'django.core.mail.backends.locmem.EmailBackend':
        # We don't want to send emails to localhost or example.org in production,
        # but we'll allow it in development setups for easier testing.
        # However, we do want to "send" mails in test environments where they go
        # to the django test outbox.
        to = [addr for addr in to if not any([addr.endswith(domain) for domain in DEBUG_DOMAINS])]
    if not to:
        return
    reply_to = reply_to.split(',') if isinstance(reply_to, str) else (reply_to or [])
    reply_to = [addr for addr in reply_to if addr]
    reply_to = reply_to or []

    if event:
        event = Event.objects.get(pk=event)
        backend = event.get_mail_backend()

        sender = settings.MAIL_FROM
        if event.mail_settings['smtp_use_custom']:  # pragma: no cover
            sender = event.mail_settings['mail_from'] or sender

        # Use unified Reply-To resolution
        if not reply_to:
            reply_to = get_reply_to_address(
                event,
                override=reply_to,
                use_custom_smtp=event.mail_settings['smtp_use_custom'],
                auto_email=False  # Legacy path is typically manual
            )

        if isinstance(reply_to, str):
            reply_to = [formataddr((str(event.name), reply_to))]

        sender = formataddr((str(event.name), sender or settings.MAIL_FROM))

    else:
        sender = formataddr(('eventyay', settings.MAIL_FROM))
        backend = get_connection(fail_silently=False)

    email = EmailMultiAlternatives(
        subject,
        body,
        sender,
        to=to,
        cc=cc,
        bcc=bcc,
        headers=headers or {},
        reply_to=reply_to,
    )
    if html is not None:
        import css_inline

        inliner = css_inline.CSSInliner(keep_style_tags=False)
        body_html = inliner.inline(html)

        email.attach_alternative(body_html, 'text/html')

    if attachments:
        for attachment in attachments:
            with suppress(Exception):
                email.attach(
                    attachment['name'],
                    attachment['content'],
                    attachment['content_type'],
                )

    try:
        backend.send_messages([email])
    except SMTPResponseException as exception:  # pragma: no cover
        # Retry on external problems: Connection issues (101, 111), timeouts (421), filled-up mailboxes (422),
        # out of memory (431), network issues (442), another timeout (447), or too many mails sent (452)
        if exception.smtp_code in (101, 111, 421, 422, 431, 442, 447, 452):
            self.retry(max_retries=5, countdown=2 ** (self.request.retries * 2))
        logger.exception('Error sending email')
        raise SendMailException(f'Failed to send an email to {to}: {exception}')
    except Exception as exception:  # pragma: no cover
        logger.exception('Error sending email')
        raise SendMailException(f'Failed to send an email to {to}: {exception}')


def get_reply_to_address(
    event,
    *,
    override=None,
    template=None,
    auto_email=False,
    use_custom_smtp=False
):
    """
    Resolve Reply-To email address with unified precedence across all components.
    
    This function consolidates Reply-To logic that was previously scattered across
    tickets (base/services/mail.py), talks (base/models/mail.py), and plugins.
    
    Precedence (highest to lowest):
    1. Explicit override parameter (manual emails, highest priority)
    2. Template-level reply_to (talk/CfP specific templates)
    3. Custom SMTP reply_to (event.mail_settings['reply_to'])
    4. Event email (event.email - canonical organizer email from unification)
    5. None (let system default handle it)
    
    Note: event.settings.contact_mail is intentionally NOT used for Reply-To.
    Event.email is the canonical contact address set during event creation and
    is consistently used across tickets, talks, and all email types.
    
    Args:
        event: Event instance
        override: Explicit Reply-To address (e.g., from function parameter)
        template: MailTemplate instance (for talk/CfP emails)
        auto_email: Whether this is an automated email (vs manual)
        use_custom_smtp: Whether custom SMTP is being used
        
    Returns:
        str or None: Reply-To email address, or None if no override needed
        
    Examples:
        # Manual email with explicit override
        >>> get_reply_to_address(event, override='support@example.com')
        'support@example.com'
        
        # Talk email with template-level reply_to
        >>> get_reply_to_address(event, template=mail_template)
        'speakers@example.com'  # from template.reply_to
        
        # Auto-email using event.email
        >>> get_reply_to_address(event, auto_email=True)
        'organizer@example.com'  # from event.email
        
        # Manual email using event.email
        >>> get_reply_to_address(event)
        'organizer@example.com'  # from event.email
    """
    # 1. Explicit override (highest priority)
    if override:
        return override
    
    # 2. Template-level reply_to (talk/CfP specific)
    if template and hasattr(template, 'reply_to') and template.reply_to:
        return template.reply_to
    
    # 3. Custom SMTP reply_to
    if use_custom_smtp and event.mail_settings.get('reply_to'):
        return event.mail_settings['reply_to']
    
    # 4. Event email (canonical organizer email from unification)
    # This is the single "Organizer email address" set during event creation
    # and is used consistently across all email types (tickets, talks, etc.)
    if event.email and event.email != 'org@mail.com':
        return event.email
    
    # 5. No override - let caller use system default
    return None
