import logging

from django.db import models
from django.db.models.functions import Lower
from django.dispatch import receiver
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager, scopes_disabled

from eventyay.common.exceptions import SendMailException
from eventyay.mail.signals import queuedmail_post_send

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
        constraints = (
            models.UniqueConstraint(
                'submission',
                Lower('email'),
                name='unique_speaker_invitation_per_submission',
            ),
        )

    def __str__(self):
        return f'SpeakerInvitation(submission={self.submission.code}, email={self.email}, status={self.status})'

    def save(self, *args, **kwargs):
        self.email = (self.email or '').strip().lower()
        if (update_fields := kwargs.get('update_fields')) is not None:
            kwargs['update_fields'] = set(update_fields) | {'email'}
        return super().save(*args, **kwargs)

    @property
    def is_pending(self):
        return self.status == SpeakerInvitationStates.PENDING

    @property
    def is_delivered(self):
        if self.mail_state == SpeakerInvitationMailStates.SENT:
            return True
        return bool(self.mail and self.mail.sent)

    @property
    def can_resend(self):
        return self.is_pending and self.mail_id is not None

    @property
    def display_name(self):
        if self.user and self.user.get_display_name():
            return self.user.get_display_name()
        return self.name or self.email

    def accept(self, user=None):
        if self.status == SpeakerInvitationStates.ACCEPTED:
            return False
        accepted = now()
        user = self.user or user
        with scopes_disabled():
            updated = SpeakerInvitation.objects.filter(
                pk=self.pk, status=SpeakerInvitationStates.PENDING
            ).update(
                status=SpeakerInvitationStates.ACCEPTED,
                accepted=accepted,
                user=user,
                updated=accepted,
            )
        if not updated:
            return False
        self.status = SpeakerInvitationStates.ACCEPTED
        self.accepted = accepted
        self.user = user
        return True

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
        if mail.sent:
            self.mail_state = SpeakerInvitationMailStates.SENT
            self.save(update_fields=['mail', 'mail_state', 'updated'])
            return True

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

    def resend(self, requestor=None):
        from .mail import QueuedMail

        mail = self.mail
        if mail.sent:
            submissions = list(mail.submissions.all())
            mail = QueuedMail.objects.get(pk=mail.pk).copy_to_draft()
            mail.submissions.add(*submissions)
        return self.deliver(mail=mail, send_immediately=True, requestor=requestor)

    resend.alters_data = True

    def revoke(self, person=None, orga=True):
        with scopes_disabled():
            deleted = SpeakerInvitation.objects.filter(
                pk=self.pk, status=SpeakerInvitationStates.PENDING
            ).delete()[0]
        if not deleted:
            return False
        if self.mail and not self.mail.sent:
            self.mail.delete()
        self.submission.log_action(
            'eventyay.submission.speakers.invite.revoke',
            person=person,
            orga=orga,
            data={'email': self.email},
        )
        return True

    revoke.alters_data = True


@receiver(queuedmail_post_send)
def mark_invitation_sent(sender, mail, **kwargs):
    if not mail.pk:
        return
    with scopes_disabled():
        SpeakerInvitation.objects.filter(mail=mail).exclude(
            mail_state=SpeakerInvitationMailStates.SENT
        ).update(mail_state=SpeakerInvitationMailStates.SENT)
