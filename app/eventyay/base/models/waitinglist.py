import logging
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import OperationalError, models, transaction
from django.db.models import JSONField
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from django_scopes import ScopedManager, scope
from phonenumber_field.modelfields import PhoneNumberField

from eventyay.base.email import get_email_context
from eventyay.base.i18n import language
from eventyay.base.operational_logging import OUTCOME_FAILURE, log_event
from eventyay.base.models import Voucher
from eventyay.base.services.locking import LockReleaseException, LockTimeoutException
from eventyay.base.services.mail import mail
from eventyay.base.settings import PERSON_NAME_SCHEMES

from .base import LoggedModel
from .event import Event, SubEvent
from .product import Product, ProductVariation


logger = logging.getLogger(__name__)


class WaitingListException(Exception):  # NOQA: N818
    def __init__(self, *args):
        super().__init__(*args)
        log_event('tickets', 'waitinglist.error', OUTCOME_FAILURE, error_code='waitinglist_error')


class WaitingListUnavailable(WaitingListException):
    """The ticket has no remaining quota for a waiting-list reservation."""


class WaitingListBusy(WaitingListException):
    """A temporary booking or quota conflict requires another assignment attempt."""


class WaitingListEntry(LoggedModel):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='waitinglistentries',
        verbose_name=_('Event'),
    )
    subevent = models.ForeignKey(
        SubEvent,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=pgettext_lazy('subevent', 'Date'),
    )
    created = models.DateTimeField(verbose_name=_('On waiting list since'), auto_now_add=True)
    name_cached = models.CharField(
        max_length=255,
        verbose_name=_('Name'),
        blank=True,
        null=True,
    )
    name_parts = JSONField(blank=True, default=dict)
    email = models.EmailField(verbose_name=_('E-mail address'))
    phone = PhoneNumberField(null=True, blank=True, verbose_name=_('Phone number'))
    voucher = models.ForeignKey(
        'Voucher',
        verbose_name=_('Assigned voucher'),
        null=True,
        blank=True,
        related_name='waitinglistentries',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        related_name='waitinglistentries',
        on_delete=models.CASCADE,
        verbose_name=_('Product'),
        help_text=_('The product the user waits for.'),
    )
    variation = models.ForeignKey(
        ProductVariation,
        related_name='waitinglistentries',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_('Product variation'),
        help_text=_('The variation of the product selected above.'),
    )
    locale = models.CharField(max_length=190, default='en')
    priority = models.IntegerField(default=0)

    objects = ScopedManager(organizer='event__organizer')

    class Meta:
        verbose_name = _('Waiting list entry')
        verbose_name_plural = _('Waiting list entries')
        ordering = ('-priority', 'created')

    def __str__(self):
        return '%s waits for %s' % (str(self.email), str(self.product))

    def clean(self):
        WaitingListEntry.clean_duplicate(self.email, self.product, self.variation, self.subevent, self.pk)
        WaitingListEntry.clean_productvar(self.event, self.product, self.variation)
        WaitingListEntry.clean_subevent(self.event, self.subevent)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields', [])
        if 'name_parts' in update_fields:
            update_fields.append('name_cached')
        self.name_cached = self.name
        if self.name_parts is None:
            self.name_parts = {}
        super().save(*args, **kwargs)

    @property
    def name(self):
        if not self.name_parts:
            return None
        if '_legacy' in self.name_parts:
            return self.name_parts['_legacy']
        if '_scheme' in self.name_parts:
            scheme = PERSON_NAME_SCHEMES[self.name_parts['_scheme']]
        else:
            scheme = PERSON_NAME_SCHEMES[self.event.settings.name_scheme]
        return scheme['concatenation'](self.name_parts).strip()

    def send_voucher(self, quota_cache=None, user=None, auth=None, *, eligible=None):
        """Hold the booking lock for one reservation, then notify the recipient."""
        reserved = False
        try:
            with self.event.lock():
                self._reserve_voucher(quota_cache, user, auth, eligible)
                reserved = True
        except (LockTimeoutException, LockReleaseException) as exc:
            if not reserved:
                raise WaitingListBusy(_('The event is busy. Please try again.')) from exc
        except OperationalError as exc:
            if not reserved:
                cause = exc.__cause__
                if (getattr(cause, 'sqlstate', None) or getattr(cause, 'pgcode', None)) != '55P03':
                    raise
                raise WaitingListBusy(_('The event is busy. Please try again.')) from exc
            logger.exception('Booking lock release failed after waiting-list reservation')

        with language(self.locale, self.event.settings.region):
            mail(
                self.email,
                _('You have been selected from the waitinglist for {event}').format(event=str(self.event)),
                self.event.settings.mail_text_waiting_list,
                get_email_context(event=self.event, waiting_list_entry=self),
                self.event,
                locale=self.locale,
            )

    def _reserve_voucher(self, quota_cache, user, auth, eligible):
        """Check the current entry and quota capacity before creating its voucher."""
        with scope(event=self.event, organizer=self.event.organizer), transaction.atomic():
            try:
                self.refresh_from_db(from_queryset=type(self).objects.select_for_update(of=('self',)))
            except type(self).DoesNotExist as exc:
                raise WaitingListException(_('Waiting list entry not found.')) from exc
            if self.voucher_id:
                raise WaitingListException(_('A voucher has already been sent to this person.'))
            if '@' not in self.email:
                raise WaitingListException(_('This entry is anonymized and can no longer be used.'))
            if eligible is not None and not eligible(self):
                raise WaitingListException(_('This waiting list entry is no longer eligible.'))

            # A new quota link must validate its foreign key against this row.
            model, pk = (ProductVariation, self.variation_id) if self.variation_id else (Product, self.product_id)
            target = model.objects.select_for_update(of=('self',)).get(pk=pk)
            # An editor may already hold a quota lock while waiting to link it to the target.
            quotas = target.quotas.order_by('pk').select_for_update(of=('self',), nowait=True)
            if self.subevent_id:
                quotas = quotas.filter(subevent_id=self.subevent_id)
            target._subevent_quotas = list(quotas)
            if quota_cache is not None:
                for quota in target._subevent_quotas:
                    quota_cache.pop(quota.pk, None)
            availability = target.check_quotas(count_waitinglist=False, subevent=self.subevent, _cache=quota_cache)
            if availability[1] is not None and availability[1] < 1:
                raise WaitingListUnavailable(_('This product is currently not available.'))

            v = Voucher.objects.create(
                event=self.event,
                max_usages=1,
                valid_until=now() + timedelta(hours=self.event.settings.waiting_list_hours),
                product=self.product,
                variation=self.variation,
                tag='waiting-list',
                comment=_('Automatically created from waiting list entry for {email}').format(email=self.email),
                block_quota=True,
                subevent=self.subevent,
            )
            v.log_action(
                'eventyay.voucher.added.waitinglist',
                {
                    'product': self.product.pk,
                    'variation': self.variation.pk if self.variation else None,
                    'tag': 'waiting-list',
                    'block_quota': True,
                    'valid_until': v.valid_until.isoformat(),
                    'max_usages': 1,
                    'email': self.email,
                    'waitinglistentry': self.pk,
                    'subevent': self.subevent.pk if self.subevent else None,
                },
                user=user,
                auth=auth,
            )
            self.log_action('eventyay.waitinglist.voucher', user=user, auth=auth)
            self.voucher = v
            self.save()

    @staticmethod
    def clean_productvar(event, product, variation):
        if event != product.event:
            raise ValidationError(_('The selected product does not belong to this event.'))
        if product.has_variations and (not variation or variation.product != product):
            raise ValidationError(_('Please select a specific variation of this product.'))

    @staticmethod
    def clean_subevent(event, subevent):
        if event.has_subevents:
            if not subevent:
                raise ValidationError(_('Subevent cannot be null for event series.'))
            if event != subevent.event:
                raise ValidationError(_('The subevent does not belong to this event.'))
        else:
            if subevent:
                raise ValidationError(_('The subevent does not belong to this event.'))

    @staticmethod
    def clean_duplicate(email, product, variation, subevent, pk):
        if (
            WaitingListEntry.objects.filter(
                product=product,
                variation=variation,
                email__iexact=email,
                voucher__isnull=True,
                subevent=subevent,
            )
            .exclude(pk=pk)
            .exists()
        ):
            raise ValidationError(
                _(
                    'You are already on this waiting list! We will notify '
                    'you as soon as we have a ticket available for you.'
                )
            )
