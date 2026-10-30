import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from eventyay.base.forms.organizer_request import validate_request_slug
from eventyay.base.models import Organizer, OrganizerRequest, User
from eventyay.base.services.mail import SendMailException, mail
from eventyay.base.services.organizer_creation import create_core_team


logger = logging.getLogger(__name__)


def absolute_url(path: str) -> str:
    return settings.SITE_URL.rstrip('/') + path


def notify(email: str, subject: str, body: str) -> None:
    try:
        mail(email, subject, 'pretixcontrol/email/organizer_request.txt', {'body': body})
    except SendMailException:
        logger.exception('Could not send organiser request notification')


def notify_approval(
    application: OrganizerRequest,
    *,
    organizer_url: str,
    setup_url: str | None = None,
) -> None:
    template = (
        'pretixcontrol/email/organizer_request_approved_new_account.txt'
        if application.new_account
        else 'pretixcontrol/email/organizer_request_approved_existing_account.txt'
    )
    context = {
        'email': application.user.email,
        'organizer_name': application.organizer_name,
        'organizer_url': organizer_url,
    }
    if setup_url:
        context.update(
            {
                'password_reset_timeout_hours': settings.PASSWORD_RESET_TIMEOUT // 3600,
                'setup_url': setup_url,
            }
        )

    try:
        mail(
            application.email,
            _('Your organiser request has been approved'),
            template,
            context,
            locale=application.user.locale,
            user=application.user,
        )
    except SendMailException:
        logger.exception('Could not send organiser request approval to %s', application.email)
    else:
        logger.info('Submitted organiser request approval for delivery to %s', application.email)


def notify_submission(application: OrganizerRequest) -> None:
    notify(
        application.email,
        _('Organiser request received'),
        _('Thank you for your request. We will review it within a few business days.'),
    )
    review_url = absolute_url(reverse('eventyay_admin:admin.organizer_requests.detail', args=[application.pk]))
    body = _('A new organiser request is ready for review.\n\nReview: {url}').format(url=review_url)
    for email in User.objects.filter(
        Q(is_staff=True) | Q(is_superuser=True), is_active=True, is_spam=False
    ).values_list('email', flat=True):
        notify(email, _('New organiser request'), body)


@transaction.atomic
def review_request(
    pk: int, reviewer: User, *, approve: bool, organizer_name: str = '', slug: str = '', reason: str = ''
) -> OrganizerRequest:
    application = OrganizerRequest.objects.select_for_update().get(pk=pk)
    if application.status != OrganizerRequest.Status.PENDING:
        raise ValidationError(_('This request has already been reviewed.'))
    if approve:
        validate_request_slug(slug, exclude_request_id=application.pk)
        user = User.objects.filter(email__iexact=application.email).first()
        if user and (not user.is_active or user.is_spam):
            raise ValidationError(_('This account is inactive or marked as spam and cannot be granted access.'))
        application.new_account = user is None
        if user is None:
            user = User.objects.create_user(email=application.email, fullname=application.name)
        organizer = Organizer(name=organizer_name, slug=slug)
        organizer.full_clean()
        organizer.save()
        create_core_team(organizer, user)
        if not user.default_organizer_id:
            user.default_organizer = organizer
            user.save(update_fields=['default_organizer'])
        application.organizer_name = organizer_name
        application.slug = slug
        application.organizer = organizer
        application.user = user
        application.status = OrganizerRequest.Status.APPROVED
        url = absolute_url(reverse('control:organizer', kwargs={'organizer': slug}))
        setup_url = None
        if application.new_account:
            params = urlencode({'id': user.pk, 'token': default_token_generator.make_token(user)})
            setup_url = absolute_url(reverse('eventyay_common:auth.forgot.recover')) + '?' + params
    else:
        application.status = OrganizerRequest.Status.REJECTED
        application.reason = reason
        subject = _('Your organiser request has been rejected')
        body = _('Your organiser request has been rejected.')
        if reason:
            body += '\n\n' + _('Reason: {reason}').format(reason=reason)
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()
    application.save()
    if approve:
        transaction.on_commit(lambda: notify_approval(application, organizer_url=url, setup_url=setup_url))
    else:
        transaction.on_commit(lambda: notify(application.email, subject, body))
    return application
