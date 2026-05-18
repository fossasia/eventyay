import logging
import smtplib

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views import View

from . import EventViewMixin

logger = logging.getLogger(__name__)


class ContactOrganizerView(EventViewMixin, View):
    """Accept a contact-organizer message and forward it via email."""

    def post(self, request, *args, **kwargs):
        message = request.POST.get('message', '').strip()
        sender_email = request.POST.get('email', '').strip()

        if request.user.is_authenticated and request.user.email:
            sender_email = request.user.email

        if not message:
            return JsonResponse(
                {'success': False, 'error': _('Please enter a message.')},
                status=400,
            )

        if not sender_email:
            return JsonResponse(
                {'success': False, 'error': _('Please enter your email address.')},
                status=400,
            )

        contact_email = (
            request.event.settings.contact_mail
            or getattr(request.event, 'email', None)
            or ''
        )

        if not contact_email:
            return JsonResponse(
                {'success': False, 'error': _('No contact email configured for this event.')},
                status=400,
            )

        subject = _('Message from attendee – {event}').format(
            event=str(request.event.name),
        )

        try:
            backend = request.event.get_mail_backend()
            from_addr = (
                request.event.settings.get('mail_from')
                or settings.MAIL_FROM
            )
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_addr,
                to=[contact_email],
                reply_to=[sender_email],
            )
            backend.send_messages([email])
        except (smtplib.SMTPException, ConnectionError, OSError):
            logger.exception('Failed to send contact organizer email')
            return JsonResponse(
                {'success': False, 'error': _('Failed to send message. Please try again later.')},
                status=500,
            )

        return JsonResponse({'success': True})
