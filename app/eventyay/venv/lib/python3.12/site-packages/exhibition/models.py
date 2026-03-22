import os
import secrets
import string

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from eventyay.base.models import Event
from i18nfield.fields import I18nCharField, I18nTextField
from i18nfield.strings import LazyI18nString


def generate_key():
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


def generate_booth_id(event=None):
    import random
    import string

    # Generate a random booth_id if none exists
    characters = string.ascii_letters + string.digits
    while True:
        booth_id = ''.join(random.choices(characters, k=8))  # 8-character random string
        queryset = ExhibitorInfo.objects.filter(booth_id=booth_id)
        if event is not None:
            queryset = queryset.filter(event=event)
        if not queryset.exists():
            return booth_id


def exhibitor_logo_path(instance, filename):
    name = instance.name
    if isinstance(name, LazyI18nString):
        event = getattr(instance, 'event', None)
        locale = getattr(event, 'locale', None) if event is not None else None
        name = name.localize(locale) if locale else str(name)
    return os.path.join('exhibitors', 'logos', str(name), filename)


class ExhibitorSettings(models.Model):
    event = models.ForeignKey('base.Event', on_delete=models.CASCADE)
    exhibitors_access_mail_subject = models.CharField(max_length=255)
    exhibitors_access_mail_body = models.TextField()
    allowed_fields = models.JSONField(default=list)

    @property
    def all_allowed_fields(self):
        """Return all allowed fields, including required default fields"""
        default_fields = ['attendee_name', 'attendee_email']
        return list(set(default_fields + self.allowed_fields))

    class Meta:
        unique_together = ('event',)


class ExhibitorInfo(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = I18nCharField(
        max_length=190,
        verbose_name=_('Name')
    )
    description = I18nTextField(
        verbose_name=_('Description'),
        null=True,
        blank=True
    )
    url = models.URLField(
        verbose_name=_('URL'),
        null=True,
        blank=True
    )
    email = models.EmailField(
        verbose_name=_('Email'),
        null=True,
        blank=True
    )
    logo = models.ImageField(
        upload_to=exhibitor_logo_path,
        null=True,
        blank=True
    )
    key = models.CharField(
        max_length=8,
        default=generate_key,
    )
    booth_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    booth_name = I18nCharField(
        max_length=100,
        verbose_name=_('Booth Name'),
    )
    lead_scanning_enabled = models.BooleanField(
        default=False
    )
    allow_voucher_access = models.BooleanField(default=False)
    allow_lead_access = models.BooleanField(default=False)
    lead_scanning_scope_by_device = models.BooleanField(default=False)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'booth_id'],
                condition=Q(booth_id__isnull=False),
                name='exhibition_event_booth_id_uniq',
            ),
        ]

    def __str__(self):
        return str(self.name)


class Lead(models.Model):
    exhibitor = models.ForeignKey(
        ExhibitorInfo,
        on_delete=models.CASCADE
    )
    exhibitor_name = models.CharField(
        max_length=190
    )
    pseudonymization_id = models.CharField(
        max_length=190
    )
    scanned = models.DateTimeField()
    scan_type = models.CharField(
        max_length=50
    )
    device_name = models.CharField(
        max_length=50
    )
    attendee = models.JSONField(
        null=True,
        blank=True
    )
    booth_id = models.CharField(
        max_length=100,
        editable=True
    )
    booth_name = models.CharField(
        max_length=100,
        verbose_name=_('Booth Name'),
    )

    def __str__(self):
        return f"Lead scanned by {self.exhibitor.name}"


class ExhibitorTag(models.Model):
    exhibitor = models.ForeignKey(
        ExhibitorInfo,
        on_delete=models.CASCADE,
        related_name='tags'
    )
    name = models.CharField(max_length=50)
    use_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('exhibitor', 'name')
        ordering = ['-use_count', 'name']

    def __str__(self):
        return f"{self.name} ({self.exhibitor.name})"
