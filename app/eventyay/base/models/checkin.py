from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, F, JSONField, Max, OuterRef, Q, Subquery
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from django_scopes import ScopedManager, scopes_disabled

from eventyay.base.models import LoggedModel
from eventyay.base.models.fields import MultiStringField


class CheckinList(LoggedModel):
    event = models.ForeignKey('Event', related_name='checkin_lists', on_delete=models.CASCADE)
    name = models.CharField(max_length=190)
    all_products = models.BooleanField(default=True, verbose_name=_('All products (including newly created ones)'))
    limit_products = models.ManyToManyField('Product', verbose_name=_('Limit to products'), blank=True)
    subevent = models.ForeignKey(
        'SubEvent',
        null=True,
        blank=True,
        verbose_name=pgettext_lazy('subevent', 'Date'),
        on_delete=models.CASCADE,
    )
    include_pending = models.BooleanField(
        verbose_name=pgettext_lazy('checkin', 'Include pending orders'),
        default=False,
        help_text=_('With this option, people will be able to check in even if the order has not been paid.'),
    )
    gates = models.ManyToManyField(
        'Gate',
        verbose_name=_('Gates'),
        blank=True,
        help_text=_(
            'Assign gates to devices for automatic configuration. When per-gate check-in limits are '
            'enabled, the device gate is used to enforce them.'
        ),
    )
    allow_entry_after_exit = models.BooleanField(verbose_name=_('Allow re-entering after an exit scan'), default=True)
    allow_multiple_entries = models.BooleanField(
        verbose_name=_('Allow multiple entries per ticket'),
        help_text=_('Use this option to turn off warnings if a ticket is scanned a second time.'),
        default=False,
    )
    limit_one_checkin_per_day = models.BooleanField(
        verbose_name=_('Limit to one check-in per day'),
        help_text=_('Each ticket can only be checked in once per calendar day on this list.'),
        default=True,
    )
    limit_one_checkin_per_gate = models.BooleanField(
        verbose_name=_('Limit to one check-in per gate'),
        help_text=_('Each ticket can only be checked in once per gate on this list.'),
        default=True,
    )
    display_popup_fields = JSONField(
        default=list,
        blank=True,
        verbose_name=_('Check-in app display fields'),
        help_text=_(
            'Additional attendee registration fields to display on the check-in success pop-up screen.'
        ),
    )
    exit_all_at = models.DateTimeField(verbose_name=_('Automatically check out everyone at'), null=True, blank=True)
    auto_checkin_sales_channels = MultiStringField(
        default=[],
        blank=True,
        verbose_name=_('Sales channels to automatically check in'),
        help_text=_(
            'All products on this check-in list will be automatically marked as checked-in when purchased through '
            'any of the selected sales channels. This option can be useful when tickets sold at the box office '
            'are not checked again before entry and should be considered validated directly upon purchase.'
        ),
    )
    rules = JSONField(default=dict, blank=True)

    objects = ScopedManager(organizer='event__organizer')

    class Meta:
        ordering = ('subevent__date_from', 'name')

    @property
    def positions(self):
        from . import Order, OrderPosition

        qs = OrderPosition.objects.filter(
            order__event=self.event,
            order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING]
            if self.include_pending
            else [Order.STATUS_PAID],
        )
        if self.subevent_id:
            qs = qs.filter(subevent_id=self.subevent_id)
        if not self.all_products:
            qs = qs.filter(product__in=self.limit_products.values_list('id', flat=True))
        return qs

    @property
    def positions_inside(self):
        return self.positions.annotate(
            last_entry=Subquery(
                Checkin.objects.filter(
                    position_id=OuterRef('pk'),
                    list_id=self.pk,
                    type=Checkin.TYPE_ENTRY,
                )
                .order_by()
                .values('position_id')
                .annotate(m=Max('datetime'))
                .values('m')
            ),
            last_exit=Subquery(
                Checkin.objects.filter(
                    position_id=OuterRef('pk'),
                    list_id=self.pk,
                    type=Checkin.TYPE_EXIT,
                )
                .order_by()
                .values('position_id')
                .annotate(m=Max('datetime'))
                .values('m')
            ),
        ).filter(Q(last_entry__isnull=False) & Q(Q(last_exit__isnull=True) | Q(last_exit__lt=F('last_entry'))))

    @property
    def inside_count(self):
        return self.positions_inside.count()

    @property
    @scopes_disabled()
    # Disable scopes, because this query is safe and the additional organizer filter in the EXISTS() subquery
    # tricks PostgreSQL into a bad subplan that sequentially scans all events.
    def checkin_count(self):
        return self.event.cache.get_or_set(
            'checkin_list_{}_checkin_count'.format(self.pk),
            lambda: self.positions.using(settings.DATABASE_REPLICA)
            .annotate(
                checkedin=Exists(
                    Checkin.objects.filter(
                        list_id=self.pk,
                        position=OuterRef('pk'),
                        type=Checkin.TYPE_ENTRY,
                    )
                )
            )
            .filter(checkedin=True)
            .count(),
            60,
        )

    @property
    def percent(self):
        pc = self.position_count
        return round(self.checkin_count * 100 / pc) if pc else 0

    @property
    def position_count(self):
        return self.event.cache.get_or_set(
            'checkin_list_{}_position_count'.format(self.pk),
            lambda: self.positions.count(),
            60,
        )

    def touch(self):
        self.event.cache.delete('checkin_list_{}_position_count'.format(self.pk))
        self.event.cache.delete('checkin_list_{}_checkin_count'.format(self.pk))

    @staticmethod
    def annotate_with_numbers(qs, event):
        # This is only kept for backwards-compatibility reasons. This method used to precompute .position_count
        # and .checkin_count through a huge subquery chain, but was dropped for performance reasons.
        return qs

    def __str__(self):
        return self.name

    DISPLAY_POPUP_STANDARD_FIELDS = (
        ('company', _('Company')),
        ('job_title', _('Job title')),
        ('attendee_email', _('Email')),
    )
    POPUP_STANDARD_FIELD_KEYS = frozenset(key for key, _ in DISPLAY_POPUP_STANDARD_FIELDS)

    @classmethod
    def display_popup_questions(cls, event):
        return event.questions.filter(active=True, hidden=False).order_by('position')

    @classmethod
    def display_popup_field_choices(cls, event):
        choices = list(cls.DISPLAY_POPUP_STANDARD_FIELDS)
        for question in cls.display_popup_questions(event):
            choices.append((f'question_{question.pk}', str(question.question)))
        return choices

    @classmethod
    def normalize_display_popup_field_key(cls, value):
        key = str(value or '').strip()
        if not key:
            return None
        if key in cls.POPUP_STANDARD_FIELD_KEYS:
            return key
        if key.startswith('question_'):
            return key
        if key.isdigit():
            return f'question_{key}'
        return None

    @classmethod
    def normalize_display_popup_fields(cls, values):
        if not values:
            return []
        cleaned = []
        for value in values:
            key = cls.normalize_display_popup_field_key(value)
            if key and key not in cleaned:
                cleaned.append(key)
        return cleaned

    @classmethod
    def validate_display_popup_fields(cls, event, values):
        if values is None:
            return []
        if not isinstance(values, (list, tuple)):
            raise ValidationError(_('Display fields must be a list.'))

        valid_question_ids = set(cls.display_popup_questions(event).values_list('pk', flat=True))
        cleaned = []
        for value in values:
            key = cls.normalize_display_popup_field_key(value)
            if not key:
                raise ValidationError(_('Invalid display field: {key}').format(key=value))
            if key in cls.POPUP_STANDARD_FIELD_KEYS:
                if key not in cleaned:
                    cleaned.append(key)
                continue
            try:
                question_id = int(key.split('_', 1)[1])
            except (ValueError, IndexError) as exc:
                raise ValidationError(_('Invalid question field: {key}').format(key=key)) from exc
            if question_id not in valid_question_ids:
                raise ValidationError(_('Unknown or inactive question field: {key}').format(key=key))
            if key not in cleaned:
                cleaned.append(key)
        return cleaned

    @classmethod
    def validate_rules(cls, rules, seen_nonbool=False, depth=0):
        # While we implement a full jsonlogic machine on Python-level, we also use the logic rules to generate
        # SQL queries, which is not a full implementation of JSON logic right now, but makes some assumptions,
        # e.g. it does not support something like (a AND b) == (c OR D)
        # Every change to our supported JSON logic must be done
        # * in eventyay.base.services.checkin
        # * in eventyay.base.models.checkin
        # * in checkinrules.js
        # * in libeventyaysync
        top_level_operators = {
            '<',
            '<=',
            '>',
            '>=',
            '==',
            '!=',
            'inList',
            'isBefore',
            'isAfter',
            'or',
            'and',
        }
        allowed_operators = top_level_operators | {
            'buildTime',
            'objectList',
            'lookup',
            'var',
        }
        allowed_vars = {
            'product',
            'variation',
            'now',
            'entries_number',
            'entries_today',
            'entries_days',
        }
        if not rules or not isinstance(rules, dict):
            return

        if len(rules) > 1:
            raise ValidationError(f'Rules should not include dictionaries with more than one key, found: "{rules}".')

        operator = list(rules.keys())[0]

        if operator not in allowed_operators:
            raise ValidationError(f'Logic operator "{operator}" is currently not allowed.')

        if depth == 0 and operator not in top_level_operators:
            raise ValidationError(f'Logic operator "{operator}" is currently not allowed on the first level.')

        values = rules[operator]
        if not isinstance(values, list) and not isinstance(values, tuple):
            values = [values]

        if operator == 'var':
            if values[0] not in allowed_vars:
                raise ValidationError(f'Logic variable "{values[0]}" is currently not allowed.')
            return

        if operator in ('or', 'and') and seen_nonbool:
            raise ValidationError('You cannot use OR/AND logic on a level below a comparison operator.')

        for v in values:
            cls.validate_rules(
                v,
                seen_nonbool=seen_nonbool or operator not in ('or', 'and'),
                depth=depth + 1,
            )


class Checkin(models.Model):
    """
    A check-in object is created when a person enters or exits the event.
    """

    TYPE_ENTRY = 'entry'
    TYPE_EXIT = 'exit'
    CHECKIN_TYPES = (
        (TYPE_ENTRY, _('Entry')),
        (TYPE_EXIT, _('Exit')),
    )
    position = models.ForeignKey('base.OrderPosition', related_name='checkins', on_delete=models.CASCADE)
    datetime = models.DateTimeField(default=now)
    nonce = models.CharField(max_length=190, null=True, blank=True)
    list = models.ForeignKey(
        'base.CheckinList',
        related_name='checkins',
        on_delete=models.PROTECT,
    )
    type = models.CharField(max_length=100, choices=CHECKIN_TYPES, default=TYPE_ENTRY)
    forced = models.BooleanField(default=False)
    device = models.ForeignKey(
        'base.Device',
        related_name='checkins',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    gate = models.ForeignKey(
        'base.Gate',
        related_name='checkins',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    auto_checked_in = models.BooleanField(default=False)

    objects = ScopedManager(organizer='position__order__event__organizer')

    class Meta:
        ordering = (('-datetime'),)

    def __repr__(self):
        return "<Checkin: pos {} on list '{}' at {}>".format(self.position, self.list, self.datetime)

    def save(self, **kwargs):
        super().save(**kwargs)
        self.position.order.touch()
        self.list.event.cache.delete('checkin_count')
        self.list.touch()

    def delete(self, **kwargs):
        super().delete(**kwargs)
        self.position.order.touch()
        self.list.touch()
