import datetime
import logging
from datetime import timedelta

import pytz

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.timezone import now
from i18nfield.fields import I18nTextField

from eventyay.base.email import get_email_context
from eventyay.base.models.auth import User
from eventyay.base.models.event import Event
from eventyay.base.models.orders import InvoiceAddress, Order, OrderPosition
from eventyay.base.i18n import LazyI18nString
from eventyay.base.services.mail import mail


logger = logging.getLogger(__name__)


class ComposingFor(models.TextChoices):
    ATTENDEES = 'attendees', 'Attendees'
    TEAMS = 'teams', 'Teams'


class Recipients(models.TextChoices):
    ORDERS = 'orders', 'Orders'
    ATTENDEES = 'attendees', 'Attendees'
    BOTH = 'both', 'Both'



class EmailQueue(models.Model):
    """
    Stores queued emails composed by organizers for later sending.

    :param event: The event this queued mail is associated with.
    :type event: Event
    :param user: The user (organizer/admin) who queued this email.
    :type user: User

    :param composing_for: To whom the organizer is composing email for. Either "attendees" or "teams"
    :type composing_for: str

    :param subject: The untranslated subject, stored as an i18n-aware string.
                        (e.g., {"en": "Hello", "de": "Hallo"}).
    :type subject: I18nTextField

    :param message: The untranslated body of the email, also i18n-aware.
    :type message: I18nTextField

    :param reply_to: Optional reply-to address to use in sent email.
    :type reply_to: str

    :param bcc: Comma-separated list of BCC recipients.
    :type bcc: str

    :param locale: Preferred default locale if not overridden per recipient.
    :type locale: str

    :param attachments: List of file UUIDs to be attached to the email.
    :type attachments: list[str]

    :param created: Timestamp of when the queued mail was created.
    :type created: datetime.datetime

    :param updated: Timestamp of the last update.
    :type updated: datetime.datetime

    :param sent_at: When the email was sent (fully completed).
    :type sent_at: datetime.datetime or None
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="email_queue")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    composing_for = models.CharField(max_length=20, choices=ComposingFor.choices, default=ComposingFor.ATTENDEES)

    subject = I18nTextField(null=True, blank=True)
    message = I18nTextField(null=True, blank=True)

    reply_to = models.CharField(max_length=100, default='', blank=True)
    bcc = models.TextField(null=True, blank=True)  # comma-separated
    locale = models.CharField(max_length=16, blank=True, default='')
    attachments = ArrayField(base_field=models.UUIDField(), blank=True, default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"EmailQueue(event={self.event.slug}, sent_at={self.sent_at})"

    def subject_localized(self, locale=None):
        """
        Returns localized subject if LazyI18nString.
        """
        subject = LazyI18nString(self.subject)
        return subject.localize(locale or self.locale or self.event.settings.locale)

    def message_localized(self, locale=None):
        """
        Returns localized message if LazyI18nString.
        """
        message = LazyI18nString(self.message)
        return message.localize(locale or self.locale or self.event.settings.locale)

    def send(self, async_send=True):
        """
        Sends queued email to each recipients.
        Uses their stored metadata and updates send status individually.
        """
        if self.sent_at:
            return False  # Already sent
        recipients = self.recipients.all()
        if not recipients.exists():
            return False  # Nothing to send

        subject = LazyI18nString(self.subject)
        message = LazyI18nString(self.message)

        for recipient in recipients:
            if recipient.sent:
                continue
            self._send_to_recipient(recipient, subject, message, async_send=async_send)

        self._finalize_send_status()
        return True

    def _build_email_context(self, order, position, position_or_address, recipient):
        try:
            if self.composing_for == ComposingFor.ATTENDEES:
                return get_email_context(
                    event=self.event,
                    order=order,
                    position=position,
                    position_or_address=position_or_address,
                )
            else:
                return get_email_context(event=self.event)
        except Exception as e:
            logger.exception("Error while generating email context")
            recipient.error = f"Context error: {str(e)}"
            recipient.save(update_fields=["error"])
            return None

    def _finalize_send_status(self):
        self.sent_at = now() if all(r.sent for r in self.recipients.all()) else None
        self.save(update_fields=["sent_at"])

    def _send_to_recipient(self, recipient, subject, message, async_send=True):
        from eventyay.base.services.mail import SendMailException
        email = recipient.email
        if not email:
            return False

        order_id = recipient.orders[0] if recipient.orders else None
        position_id = recipient.positions[0] if recipient.positions else None

        order = Order.objects.filter(pk=order_id, event=self.event).first() if order_id else None
        position = OrderPosition.objects.filter(pk=position_id).first() if position_id else None

        try:
            ia = order.invoice_address if order else None
        except InvoiceAddress.DoesNotExist:
            ia = InvoiceAddress(order=order) if order else None

        position_or_address = position or ia
        context = self._build_email_context(order, position, position_or_address, recipient)
        if context is None:
            return True  # Error already logged

        try:
            mail(
                email=email,
                subject=subject,
                template=message,
                context=context,
                event=self.event,
                locale=order.locale if order else self.locale,
                order=order,
                position=position,
                sender=self.event.settings.get('mail_from'),
                event_bcc=self.bcc,
                event_reply_to=self.reply_to,
                attach_cached_files=self.attachments,
                user=self.user,
                auto_email=False,
                sync_send=not async_send,
            )
            recipient.sent = True
            recipient.error = None
            recipient.save(update_fields=["sent", "error"])
        except SendMailException as se:
            recipient.sent = False
            recipient.error = str(se)
            recipient.save(update_fields=["sent", "error"])
            logger.exception("SendMailException error while sending to %s", email)
        except Exception as e:
            recipient.sent = False
            recipient.error = f"Internal error: {str(e)}"
            recipient.save(update_fields=["sent", "error"])
            logger.exception("Unexpected error while sending to %s", email)

        return True

    def get_recipient_emails(self):
        """
        Resolve and return the full list of unique email addresses
        this queued mail will send to.
        """
        return sorted(set(r.email.strip().lower() for r in self.recipients.all() if r.email))

    def populate_to_users(self, save=True):
        """
        Resolves recipients and populates to_users with metadata.
        """
        from collections import defaultdict

        filters = getattr(self, 'filters_data', None)
        if not filters:
            return

        recipients_mode = filters.recipients or "orders"
        orders_qs = Order.objects.filter(
            pk__in=filters.orders,
            event=self.event
        ).prefetch_related('positions__product', 'positions__addons', 'positions__checkins')

        recipients = defaultdict(lambda: {
            "orders": set(),
            "positions": set(),
            "products": set()
        })

        for order in orders_qs:
            order_fallback_needed = False
            attendee_found = False

            for pos in order.positions.all():
                if pos.attendee_email:
                    attendee_found = True
                    email = pos.attendee_email.strip().lower()
                    recipients[email]["orders"].add(order.pk)
                    recipients[email]["positions"].add(pos.pk)
                    recipients[email]["products"].add(pos.product.pk)
                else:
                    # No attendee email; maybe fallback later
                    order_fallback_needed = True

            # Fallback to order email if needed
            if (
                order_fallback_needed and
                not attendee_found and
                recipients_mode == "attendees" and
                order.email
            ):
                email = order.email.strip().lower()
                recipients[email]["orders"].add(order.pk)
                product_ids = order.positions.values_list('product__pk', flat=True)
                recipients[email]["products"].update(pid for pid in product_ids)

            # Explicit inclusion of orders
            if recipients_mode in ("both", "orders") and order.email:
                email = order.email.strip().lower()
                recipients[email]["orders"].add(order.pk)
                product_ids = order.positions.values_list('product__pk', flat=True)
                recipients[email]["products"].update(pid for pid in product_ids)

        # Clear and insert fresh records
        self.recipients.all().delete()

        objs = [
            EmailQueueToUser(
                mail=self,
                email=email,
                orders=list(data["orders"]),
                positions=list(data["positions"]),
                products=list(data["products"]),
                sent=False,
                error=None,
            )
            for email, data in recipients.items()
        ]

        EmailQueueToUser.objects.bulk_create(objs)
        if save:
            self.save()


class EmailQueueToUser(models.Model):
    """
    Represents a single recipient of a EmailQueue.

    :param mail: Reference to the parent EmailQueue.
    :type mail: EmailQueue

    :param email: Email address of the recipient.
    :type email: email
    
    :param orders: List of order IDs associated with this recipient.
    :type orders: list[int]
    
    :param positions: List of order position IDs.
    :type positions: list[int]
    
    :param products: List of product IDs associated with this user.
    :type products: list[int]
    
    :param team: Team ID if this is a team recipient.
    :type team: int or None
    
    :param sent: Whether this recipient has been successfully sent the email.
    :type sent: bool
    
    :param error: Error message if sending failed.
    :type error: str or None
    """
    mail = models.ForeignKey(EmailQueue, on_delete=models.CASCADE, related_name="recipients")
    email = models.EmailField()
    orders = ArrayField(models.BigIntegerField(), blank=True, default=list)
    positions = ArrayField(models.BigIntegerField(), blank=True, default=list)
    products = ArrayField(models.BigIntegerField(), blank=True, default=list)
    team = models.IntegerField(null=True, blank=True)
    sent = models.BooleanField(default=False)
    error = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ("mail", "email")

    def __str__(self):
        return f"{self.email} for {self.mail_id}"


class EmailQueueFilter(models.Model):
    """
    Stores structured filtering rules for recipient selection in EmailQueue.

    :param mail: Associated EmailQueue.
    :type mail: EmailQueue
    
    :param recipients: Target recipient scope: 'orders', 'attendees', or 'both'.
    :type recipients: str
    
    :param order_status: Email roles or tags to include.
    :type order_status: list[str]
    
    :param products: Filter by product IDs.
    :type products: list[int]
    
    :param checkin_lists: Check-in list IDs to filter by.
    :type checkin_lists: list[int]
    
    :param has_filter_checkins: Whether to filter based on check-in status.
    :type has_filter_checkins: bool
    
    :param not_checked_in: Whether to include only recipients who haven’t checked in.
    :type not_checked_in: bool
    
    :param subevent: Specific subevent ID to target.
    :type subevent: int or None
    
    :param subevents_from: Filter subevents from this date/time onward.
    :type subevents_from: datetime.datetime or None
    
    :param subevents_to: Filter subevents up to this date/time.
    :type subevents_to: datetime.datetime or None
    
    :param order_created_from: Include orders created after this date/time.
    :type order_created_from: datetime.datetime or None
    
    :param order_created_to: Include orders created before this date/time.
    :type order_created_to: datetime.datetime or None
    
    :param orders: Explicit order IDs to include.
    :type orders: list[int]
    
    :param teams: Team IDs to include (for team-based emails).
    :type teams: list[int]
    """
    mail = models.OneToOneField(EmailQueue, on_delete=models.CASCADE, related_name="filters_data")

    recipients = models.CharField(max_length=10, choices=Recipients.choices, default=Recipients.ORDERS, blank=True)
    order_status = ArrayField(models.CharField(max_length=20), blank=True, default=list)
    products = ArrayField(models.BigIntegerField(), blank=True, default=list)
    checkin_lists = ArrayField(models.IntegerField(), blank=True, default=list)
    has_filter_checkins = models.BooleanField(default=False)
    not_checked_in = models.BooleanField(default=False)
    subevent = models.IntegerField(null=True, blank=True)
    subevents_from = models.DateTimeField(null=True, blank=True)
    subevents_to = models.DateTimeField(null=True, blank=True)
    order_created_from = models.DateTimeField(null=True, blank=True)
    order_created_to = models.DateTimeField(null=True, blank=True)
    orders = ArrayField(models.IntegerField(), blank=True, default=list)
    teams = ArrayField(models.IntegerField(), blank=True, default=list)

    def __str__(self):
        return f"Filters for mail {self.mail_id}"


class ScheduleType(models.TextChoices):
    ABSOLUTE = 'absolute', 'Absolute'
    RELATIVE_BEFORE_EVENT_START = 'relative_before_event_start', 'Relative, before event start'
    RELATIVE_BEFORE_EVENT_END = 'relative_before_event_end', 'Relative, before event end'
    RELATIVE_AFTER_EVENT_START = 'relative_after_event_start', 'Relative, after event start'
    RELATIVE_AFTER_EVENT_END = 'relative_after_event_end', 'Relative, after event end'


class ScheduledMail(models.Model):
    """
    A scheduling rule that automatically sends emails to event attendees
    at a configured time (absolute or relative to event dates).

    :param event: The event this rule belongs to.
    :param enabled: Only enabled rules are processed by the periodic task.
    :param subject: I18n email subject template.
    :param message: I18n email body template.
    :param recipients: Who to send to: orders / attendees / both.
    :param order_status: Filter by order status codes.
    :param products: Filter by product IDs.
    :param checkin_lists: Filter by check-in list IDs.
    :param has_filter_checkins: Whether the check-in filter is active.
    :param not_checked_in: If True, target only attendees NOT checked in.
    :param subevent: Restrict to a specific subevent ID.
    :param schedule_type: How the send time is computed.
    :param send_date: Absolute send datetime (used when schedule_type=absolute).
    :param send_offset_days: Days before/after event for relative schedule.
    :param send_offset_time: Wall-clock time on that day for relative schedule.
    :param last_execution: Timestamp of the last time this rule fired for this event cycle.
    """

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='scheduled_mails',
    )
    enabled = models.BooleanField(default=True)

    # Content
    subject = I18nTextField(null=True, blank=True)
    message = I18nTextField(null=True, blank=True)

    # Recipient settings
    recipients = models.CharField(
        max_length=10,
        choices=Recipients.choices,
        default=Recipients.ORDERS,
    )

    # Filters — mirror EmailQueueFilter fields
    order_status = ArrayField(models.CharField(max_length=20), blank=True, default=list)
    products = ArrayField(models.BigIntegerField(), blank=True, default=list)
    checkin_lists = ArrayField(models.IntegerField(), blank=True, default=list)
    has_filter_checkins = models.BooleanField(default=False)
    not_checked_in = models.BooleanField(default=False)
    subevent = models.IntegerField(null=True, blank=True)

    # Schedule
    schedule_type = models.CharField(
        max_length=40,
        choices=ScheduleType.choices,
        default=ScheduleType.ABSOLUTE,
    )
    send_date = models.DateTimeField(null=True, blank=True)
    send_offset_days = models.IntegerField(null=True, blank=True)
    send_offset_time = models.TimeField(null=True, blank=True)

    # Execution tracking
    last_execution = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'ScheduledMail(event={self.event.slug}, schedule_type={self.schedule_type})'

    def compute_send_datetime(self):
        """
        Compute the effective datetime when this rule should fire.
        Returns None if insufficient data is available.
        """
        from django.utils.timezone import now

        if self.schedule_type == ScheduleType.ABSOLUTE:
            return self.send_date

        event = self.event
        tz = pytz.timezone(event.settings.timezone) if event.settings.timezone else pytz.utc

        if self.schedule_type in (
            ScheduleType.RELATIVE_BEFORE_EVENT_START,
            ScheduleType.RELATIVE_AFTER_EVENT_START,
        ):
            base_dt = event.date_from
        else:  # before/after event end
            base_dt = event.date_to
            if base_dt is None:
                return None

        if self.send_offset_days is None:
            return None

        if self.schedule_type in (
            ScheduleType.RELATIVE_BEFORE_EVENT_START,
            ScheduleType.RELATIVE_BEFORE_EVENT_END,
        ):
            target_date = (base_dt - timedelta(days=self.send_offset_days)).astimezone(tz).date()
        else:
            target_date = (base_dt + timedelta(days=self.send_offset_days)).astimezone(tz).date()

        send_time = self.send_offset_time or now().time().replace(hour=9, minute=0, second=0)
        naive_dt = datetime.datetime.combine(target_date, send_time)
        return tz.localize(naive_dt)

    def is_due(self):
        """
        Returns True if this rule should fire right now.
        A rule fires if:
        - it is enabled
        - compute_send_datetime() <= now
        - it has never fired, or its last_execution was before the computed send time
          (prevents double-firing within the same scheduled window)
        """
        from django.utils.timezone import now

        if not self.enabled:
            return False

        send_dt = self.compute_send_datetime()
        if send_dt is None:
            return False

        current = now()
        if current < send_dt:
            return False

        # Already fired after this scheduled time — skip
        if self.last_execution and self.last_execution >= send_dt:
            return False

        return True


class ScheduledMailLog(models.Model):
    """
    Records each firing of a ScheduledMail rule.

    :param rule: The rule that fired.
    :param fired_at: When the task ran.
    :param recipient_count: Number of emails dispatched.
    :param error: Optional error message if the run failed.
    """

    rule = models.ForeignKey(
        ScheduledMail,
        on_delete=models.CASCADE,
        related_name='logs',
    )
    fired_at = models.DateTimeField(auto_now_add=True)
    recipient_count = models.IntegerField(default=0)
    error = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-fired_at']

    def __str__(self):
        return f'ScheduledMailLog(rule={self.rule_id}, fired_at={self.fired_at})'
