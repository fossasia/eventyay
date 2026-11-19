from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from eventyay.base.models.mixins import TimestampedModel


class OrganizerRequest(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')

    name = models.CharField(max_length=200)
    email = models.EmailField()
    affiliation = models.CharField(max_length=300, blank=True, default='')
    events = models.TextField(blank=True, default='')
    organizer_name = models.CharField(max_length=200)
    slug = models.CharField(max_length=50)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_organizer_requests',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    organizer = models.ForeignKey('Organizer', null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='organizer_requests'
    )
    new_account = models.BooleanField(default=False)

    class Meta:
        ordering = ('-created',)
        constraints = [
            models.UniqueConstraint(
                Lower('slug'), condition=models.Q(status='pending'), name='unique_pending_organizer_request_slug'
            ),
            models.UniqueConstraint(
                Lower('email'), condition=models.Q(status='pending'), name='unique_pending_organizer_request_email'
            ),
        ]


class OrganizerRequestFieldSetting(models.Model):
    key = models.CharField(max_length=32, unique=True)
    active = models.BooleanField(default=True)
    required = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('position', 'key')


class OrganizerRequestQuestion(models.Model):
    class Variant(models.TextChoices):
        STRING = 'string', _('Short text')
        TEXT = 'text', _('Long text')
        URL = 'url', _('Link')
        BOOLEAN = 'boolean', _('Yes / No')

    label = models.CharField(max_length=200, verbose_name=_('Question'))
    help_text = models.CharField(max_length=500, blank=True, verbose_name=_('Help text'))
    variant = models.CharField(
        max_length=16, choices=Variant.choices, default=Variant.STRING, verbose_name=_('Answer type')
    )
    required = models.BooleanField(default=False, verbose_name=_('Required'))
    active = models.BooleanField(default=True, verbose_name=_('Active'))
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('position', 'id')

    def __str__(self) -> str:
        return self.label


class OrganizerRequestAnswer(models.Model):
    request = models.ForeignKey(OrganizerRequest, related_name='answers', on_delete=models.CASCADE)
    question = models.ForeignKey(OrganizerRequestQuestion, related_name='answers', on_delete=models.PROTECT)
    answer = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('request', 'question'), name='unique_organizer_request_answer'),
        ]
