import logging

import nh3
from django.conf import settings as django_settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from eventyay.base.models.auth import User
from eventyay.base.models.base import CachedFile

logger = logging.getLogger(__name__)

ALLOWED_HTML_TAGS = frozenset({
    'b', 'i', 'u', 'a', 'p', 'br', 'strong', 'em',
    'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'pre', 'code', 'hr',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img', 'span', 'div',
})


class AdminRecipientGroup(models.TextChoices):
    ALL_USERS = 'all_users', _('All registered users')
    ALL_ORGANISERS = 'all_organisers', _('All organisers')
    EVENT_ORGANISERS = 'event_organisers', _('Organisers of selected events')
    EVENT_TEAM_MEMBERS = 'event_team_members', _('Event team members')
    SPEAKERS = 'speakers', _('Speakers')
    REVIEWERS = 'reviewers', _('Reviewers')
    ATTENDEES = 'attendees', _('Attendees')
    SELECTED_USERS = 'selected_users', _('Selected users')


class AdminEmailStatus(models.TextChoices):
    DRAFT = 'draft', _('Draft')
    QUEUED = 'queued', _('Queued')
    SENDING = 'sending', _('Sending')
    SENT = 'sent', _('Sent')
    CANCELLED = 'cancelled', _('Cancelled')


class AdminEmailQueue(models.Model):
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='admin_email_queue',
        verbose_name=_('Created by'),
    )

    recipient_group = models.CharField(
        max_length=30,
        choices=AdminRecipientGroup.choices,
        default=AdminRecipientGroup.ALL_USERS,
        verbose_name=_('Recipient group'),
    )

    subject = models.CharField(max_length=500, blank=True, default='', verbose_name=_('Subject'))
    message = models.TextField(blank=True, default='', verbose_name=_('Message'))

    reply_to = models.CharField(max_length=254, blank=True, default='', verbose_name=_('Reply-To'))
    bcc = models.TextField(blank=True, default='', verbose_name=_('BCC'))

    status = models.CharField(
        max_length=20,
        choices=AdminEmailStatus.choices,
        default=AdminEmailStatus.DRAFT,
        db_index=True,
        verbose_name=_('Status'),
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_('Scheduled for'),
    )
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Sent at'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    attachment = models.UUIDField(null=True, blank=True, verbose_name=_('Attachment'))

    recipient_count_snapshot = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Recipient count at save time'),
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Admin email')
        verbose_name_plural = _('Admin emails')

    def __str__(self) -> str:
        return f'AdminEmailQueue(pk={self.pk}, subject={self.subject!r}, status={self.status})'

    @property
    def is_draft(self) -> bool:
        return self.status == AdminEmailStatus.DRAFT

    @property
    def is_sent(self) -> bool:
        return self.status == AdminEmailStatus.SENT

    def get_edit_url(self) -> str:
        return reverse('eventyay_admin:admin.messages.compose') + f'?draft={self.pk}'

    def get_recipient_count(self) -> int:
        return self.recipients.count()

    def get_sent_count(self) -> int:
        return self.recipients.filter(sent=True).count()

    def get_failed_count(self) -> int:
        return self.recipients.filter(sent=False, error__isnull=False).exclude(error='').count()

    def duplicate(self) -> 'AdminEmailQueue':
        """Create a draft copy of this email."""
        new_mail = AdminEmailQueue.objects.create(
            user=self.user,
            recipient_group=self.recipient_group,
            subject=self.subject,
            message=self.message,
            reply_to=self.reply_to,
            bcc=self.bcc,
            status=AdminEmailStatus.DRAFT,
            attachment=self.attachment,
        )
        filters = getattr(self, 'filters', None)
        if filters:
            AdminEmailQueueFilter.objects.create(
                mail=new_mail,
                account_status=filters.account_status,
                user_role=filters.user_role,
                language=filters.language,
                created_after=filters.created_after,
                created_before=filters.created_before,
                last_active_after=filters.last_active_after,
                last_active_before=filters.last_active_before,
                event_status=filters.event_status,
                event_date_from=filters.event_date_from,
                event_date_to=filters.event_date_to,
                event_ids=list(filters.event_ids),
                organiser_ids=list(filters.organiser_ids),
                selected_user_ids=list(filters.selected_user_ids),
                organiser_status=filters.organiser_status,
                billing_status=filters.billing_status,
                ticketing_status=filters.ticketing_status,
                cfp_status=filters.cfp_status,
                setup_status=filters.setup_status,
                exclude_admins=filters.exclude_admins,
                exclude_inactive=filters.exclude_inactive,
                exclude_unconfirmed_email=filters.exclude_unconfirmed_email,
            )
        return new_mail

    def _resolve_attachment(self) -> dict | None:
        if not self.attachment:
            return None
        try:
            cf = CachedFile.objects.get(id=self.attachment)
            return {
                'cached_file_id': str(cf.id),
                'name': cf.filename or 'attachment',
                'content_type': cf.type or 'application/octet-stream',
            }
        except CachedFile.DoesNotExist:
            logger.warning('CachedFile %s not found for AdminEmailQueue %s', self.attachment, self.pk)
            return None

    def send(self) -> bool:
        """
        Dispatch the queued email to all unsent recipients.
        Returns True if processing ran; False if skipped entirely.
        Called by the Celery task.
        """
        if self.status in (AdminEmailStatus.SENT, AdminEmailStatus.DRAFT):
            return False

        if self.scheduled_at and self.scheduled_at > now():
            return False

        # Only consider recipients with a valid email address.
        valid_recipients = list(
            self.recipients
            .select_related('user')
            .filter(sent=False)
            .exclude(email__isnull=True)
            .exclude(email='')
        )
        if not valid_recipients:
            self.status = AdminEmailStatus.SENT
            self.sent_at = now()
            self.save(update_fields=['status', 'sent_at'])
            return True

        self.status = AdminEmailStatus.SENDING
        self.save(update_fields=['status'])

        # Imported here to avoid circular import: common.mail → base.models.event → base.models
        from eventyay.common.mail import mail_send_task

        reply_to_addr = self.reply_to or getattr(django_settings, 'DEFAULT_FROM_EMAIL', '')
        bcc_list = [b.strip() for b in self.bcc.split(',') if b.strip()] if self.bcc else []
        attachment_meta = self._resolve_attachment()
        attachments_arg = [attachment_meta] if attachment_meta else None
        is_first_attempt = not self.recipients.filter(sent=True).exists()

        sent_ids: list[int] = []
        failed_recipients: list[AdminEmailQueueRecipient] = []

        for recipient in valid_recipients:
            context = self._build_context(recipient)
            subject = self.subject
            body = self.message

            for key, value in context.items():
                subject = subject.replace('{' + key + '}', str(value))
                body = body.replace('{' + key + '}', str(value))

            try:
                mail_send_task.apply_async(
                    kwargs={
                        'to': [recipient.email],
                        'subject': subject,
                        'body': body,
                        'html': AdminEmailQueue.make_html(body),
                        'reply_to': [reply_to_addr] if reply_to_addr else [],
                        'event': None,
                        'cc': [],
                        'bcc': [],
                        'attachments': attachments_arg,
                    },
                    ignore_result=True,
                )
                sent_ids.append(recipient.pk)
            except Exception as exc:
                logger.exception('Error dispatching admin email to %s', recipient.email)
                recipient.error = str(exc)
                failed_recipients.append(recipient)

        if sent_ids:
            AdminEmailQueueRecipient.objects.filter(pk__in=sent_ids).update(sent=True, error=None)
        if failed_recipients:
            AdminEmailQueueRecipient.objects.bulk_update(failed_recipients, ['error'])

        if bcc_list and sent_ids and is_first_attempt:
            platform_context = {
                'platform_name': str(getattr(django_settings, 'PLATFORM_NAME', 'Eventyay')),
                'platform_url': str(getattr(django_settings, 'SITE_URL', '')),
                'support_email': str(getattr(django_settings, 'SUPPORT_EMAIL', '')),
                'support_url': str(getattr(django_settings, 'SUPPORT_URL', '')),
            }
            bcc_subject = self.subject
            bcc_body = self.message
            for key, value in platform_context.items():
                bcc_subject = bcc_subject.replace('{' + key + '}', str(value))
                bcc_body = bcc_body.replace('{' + key + '}', str(value))

            for bcc_addr in bcc_list:
                try:
                    mail_send_task.apply_async(
                        kwargs={
                            'to': [bcc_addr],
                            'subject': bcc_subject,
                            'body': bcc_body,
                            'html': AdminEmailQueue.make_html(bcc_body),
                            'reply_to': [reply_to_addr] if reply_to_addr else [],
                            'event': None,
                            'cc': [],
                            'bcc': [],
                            'attachments': attachments_arg,
                        },
                        ignore_result=True,
                    )
                except Exception:
                    logger.exception('Error dispatching BCC copy to %s for AdminEmailQueue %s', bcc_addr, self.pk)

        has_unsent = (
            self.recipients
            .filter(sent=False)
            .exclude(email__isnull=True)
            .exclude(email='')
            .exists()
        )
        if not has_unsent:
            self.status = AdminEmailStatus.SENT
            self.sent_at = now()
            self.scheduled_at = None
            self.save(update_fields=['status', 'sent_at', 'scheduled_at'])
        else:
            self.status = AdminEmailStatus.QUEUED
            self.save(update_fields=['status'])
            raise RuntimeError(
                f'AdminEmailQueue {self.pk}: dispatch incomplete — unsent recipients remain. Celery will retry.'
            )

        return True

    def _build_context(self, recipient: 'AdminEmailQueueRecipient') -> dict[str, str]:
        context: dict[str, str] = {
            'platform_name': str(getattr(django_settings, 'PLATFORM_NAME', 'Eventyay')),
            'platform_url': str(getattr(django_settings, 'SITE_URL', '')),
            'support_email': str(getattr(django_settings, 'SUPPORT_EMAIL', '')),
            'support_url': str(getattr(django_settings, 'SUPPORT_URL', '')),
        }

        user = recipient.user
        if user:
            context['user_name'] = user.get_full_name() or user.email or ''
            context['first_name'] = (user.fullname or '').split(' ')[0] if user.fullname else ''
            context['last_name'] = ' '.join((user.fullname or '').split(' ')[1:]) if user.fullname else ''
            context['email'] = user.email or ''
            context['account_url'] = ''
        elif recipient.email:
            context['user_name'] = recipient.name or recipient.email
            context['first_name'] = ''
            context['last_name'] = ''
            context['email'] = recipient.email
            context['account_url'] = ''

        return context

    @staticmethod
    def make_html(body_text: str) -> str:
        safe_body = nh3.clean(body_text, tags=ALLOWED_HTML_TAGS)
        return (
            '<!DOCTYPE html>\n'
            '<html>\n<head><meta charset="utf-8"></head>\n'
            '<body>\n'
            f'{safe_body}\n'
            '</body>\n</html>'
        )

    send.alters_data = True
    duplicate.alters_data = True


class AdminEmailQueueRecipient(models.Model):
    mail = models.ForeignKey(
        AdminEmailQueue,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    email = models.EmailField(verbose_name=_('Email'))
    name = models.CharField(max_length=255, blank=True, default='')
    reason = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_('Reason included'),
    )
    sent = models.BooleanField(default=False)
    error = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('mail', 'email')
        ordering = ['email']

    def __str__(self) -> str:
        return f'{self.email} for AdminEmailQueue#{self.mail_id}'


class AdminEmailQueueFilter(models.Model):
    mail = models.OneToOneField(
        AdminEmailQueue,
        on_delete=models.CASCADE,
        related_name='filters',
    )

    account_status = models.CharField(max_length=20, blank=True, default='', verbose_name=_('Account status'))
    user_role = models.CharField(max_length=20, blank=True, default='', verbose_name=_('User role'))
    language = models.CharField(max_length=20, blank=True, default='', verbose_name=_('Language / locale'))
    created_after = models.DateTimeField(null=True, blank=True)
    created_before = models.DateTimeField(null=True, blank=True)
    last_active_after = models.DateTimeField(null=True, blank=True)
    last_active_before = models.DateTimeField(null=True, blank=True)

    event_status = models.CharField(max_length=20, blank=True, default='')
    event_date_from = models.DateField(null=True, blank=True)
    event_date_to = models.DateField(null=True, blank=True)
    event_ids = ArrayField(models.IntegerField(), blank=True, default=list)
    organiser_ids = ArrayField(models.IntegerField(), blank=True, default=list)

    selected_user_ids = ArrayField(models.IntegerField(), blank=True, default=list)

    organiser_status = models.CharField(max_length=30, blank=True, default='')
    billing_status = models.CharField(max_length=30, blank=True, default='')
    ticketing_status = models.CharField(max_length=30, blank=True, default='')
    cfp_status = models.CharField(max_length=30, blank=True, default='')
    setup_status = models.CharField(max_length=30, blank=True, default='')

    exclude_admins = models.BooleanField(default=False, verbose_name=_('Exclude platform admins'))
    exclude_inactive = models.BooleanField(default=False, verbose_name=_('Exclude inactive users'))
    exclude_unconfirmed_email = models.BooleanField(
        default=False, verbose_name=_('Exclude users without confirmed email')
    )

    class Meta:
        verbose_name = _('Admin email filter')

    def __str__(self) -> str:
        return f'AdminEmailQueueFilter for mail {self.mail_id}'
