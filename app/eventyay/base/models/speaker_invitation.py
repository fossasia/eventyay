import logging

from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager

from eventyay.common.exceptions import SendMailException

from .mixins import PretalxModel


logger = logging.getLogger(__name__)


class SpeakerInvitationStates(models.TextChoices):
    PENDING = 'pending', _('Pending')
    ACCEPTED = 'accepted', _('Accepted')


class SpeakerInvitationMailStates(models.TextChoices):
    NOT_SENT = 'not_sent', _('Not sent')
    QUEUED = 'queued', _('Queued in Outbox')
    SENT = 'sent', _('Sent')
    FAILED = 'failed', _('Failed')


class SpeakerInvitation(PretalxModel):
    """Tracks a speaker invitation to a proposal and the delivery of its email.

    The invitation stays ``pending`` until the invited person accepts it or
    finishes setting up the account that was created for them. The delivery
    state of the invitation email is tracked separately, so an invitation can
    be pending while its email failed to send.
    """

    submission = models.ForeignKey(
        to='Submission',
        related_name='speaker_invitations',
        on_delete=models.CASCADE,
    )
    email = models.EmailField(verbose_name=_('Speaker email'))
    name = models.CharField(max_length=200, blank=True, verbose_name=_('Speaker name'))
    user = models.ForeignKey(
        to='User',
        related_name='speaker_invitations',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    invited_by = models.ForeignKey(
        to='User',
        related_name='+',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(
        max_length=16,
        choices=SpeakerInvitationStates.choices,
        default=SpeakerInvitationStates.PENDING,
    )
    mail_state = models.CharField(
        max_length=16,
        choices=SpeakerInvitationMailStates.choices,
        default=SpeakerInvitationMailStates.NOT_SENT,
    )
    mail = models.ForeignKey(
        to='QueuedMail',
        related_name='+',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    accepted = models.DateTimeField(null=True, blank=True)

    objects = ScopedManager(event='submission__event')

    class Meta:
        ordering = ('created',)
        unique_together = (('submission', 'email'),)

    def __str__(self):
        return f'SpeakerInvitation(submission={self.submission.code}, email={self.email}, status={self.status})'

    @property
    def is_pending(self):
        return self.status == SpeakerInvitationStates.PENDING

    @property
    def can_resend(self):
        return self.is_pending and self.mail_state != SpeakerInvitationMailStates.SENT

    @property
    def display_name(self):
        if self.user and self.user.get_display_name():
            return self.user.get_display_name()
        return self.name or self.email

    def accept(self, user=None):
        if self.status == SpeakerInvitationStates.ACCEPTED:
            return
        self.status = SpeakerInvitationStates.ACCEPTED
        self.accepted = now()
        if user and not self.user:
            self.user = user
        self.save(update_fields=['status', 'accepted', 'user', 'updated'])

    accept.alters_data = True

    def deliver(self, mail=None, send_immediately=True, requestor=None):
        """Sends the invitation email, or leaves it in the Outbox.

        Returns ``True`` when the email was handed to the mail backend, and
        ``False`` when sending was attempted and failed. Returns ``None`` when
        the email was only queued in the Outbox.
        """
        mail = mail or self.mail
        if not mail:
            self.mail_state = SpeakerInvitationMailStates.NOT_SENT
            self.save(update_fields=['mail_state', 'updated'])
            return False

        self.mail = mail
        if not send_immediately:
            self.mail_state = SpeakerInvitationMailStates.QUEUED
            self.save(update_fields=['mail', 'mail_state', 'updated'])
            return None

        try:
            mail.send(requestor=requestor, synchronous=True)
        except SendMailException:
            logger.exception(
                'Could not send speaker invitation for proposal %s to %s',
                self.submission.code,
                self.email,
            )
            self.mail_state = SpeakerInvitationMailStates.FAILED
            self.save(update_fields=['mail', 'mail_state', 'updated'])
            return False

        self.mail_state = SpeakerInvitationMailStates.SENT
        self.save(update_fields=['mail', 'mail_state', 'updated'])
        return True

    deliver.alters_data = True
