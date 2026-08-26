import logging
from datetime import date, timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.utils import OperationalError, ProgrammingError
from django.utils.timezone import localdate, localtime, now
from django.utils.translation import gettext_lazy as _

from eventyay.base.gmail.constants import (
    DEFAULT_GMAIL_DAILY_SEND_LIMIT,
    DEFAULT_GMAIL_RATE_LIMIT_PER_MINUTE,
)
from eventyay.base.gmail.crypto import decrypt_value, encrypt_value
from eventyay.base.models.base import LoggedModel


logger = logging.getLogger(__name__)


class GmailOAuthCredential(LoggedModel):
    event = models.ForeignKey(
        'Event',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='gmail_credentials',
        verbose_name=_('Event'),
    )
    sender_email = models.EmailField(verbose_name=_('Sender email'))
    encrypted_refresh_token = models.TextField()
    encrypted_access_token = models.TextField(blank=True, default='')
    token_expiry = models.DateTimeField(null=True, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    connected_by = models.ForeignKey(
        'User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='gmail_credentials',
    )
    daily_send_count = models.PositiveIntegerField(default=0)
    daily_send_count_date = models.DateField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Gmail OAuth credential')
        verbose_name_plural = _('Gmail OAuth credentials')
        indexes = [
            models.Index(fields=['event', 'is_active']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        scope = self.event.slug if self.event_id else _('platform')
        return f'{self.sender_email} ({scope})'

    @property
    def is_global(self) -> bool:
        return self.event_id is None

    @classmethod
    def get_active_global(cls):
        return cls.objects.filter(event__isnull=True, is_active=True).order_by('-connected_at').first()

    @classmethod
    def get_active_global_safe(cls):
        try:
            return cls.get_active_global()
        except (ProgrammingError, OperationalError):
            logger.warning('Gmail OAuth table is missing; apply database migrations.')
            return None

    @classmethod
    def get_active_for_event(cls, event):
        return cls.objects.filter(event=event, is_active=True).order_by('-connected_at').first()

    @classmethod
    def get_active_for_event_safe(cls, event):
        try:
            return cls.get_active_for_event(event)
        except (ProgrammingError, OperationalError):
            logger.warning('Gmail OAuth table is missing; apply database migrations.')
            return None

    @classmethod
    def is_table_available(cls) -> bool:
        try:
            cls.objects.exists()
        except (ProgrammingError, OperationalError):
            return False
        return True

    @classmethod
    def deactivate_for_scope(cls, *, event=None):
        qs = cls.objects.filter(is_active=True)
        if event is None:
            qs = qs.filter(event__isnull=True)
        else:
            qs = qs.filter(event=event)
        qs.update(is_active=False)

    def store_tokens(self, *, refresh_token: str, access_token: str = '', expiry=None):
        self.encrypted_refresh_token = encrypt_value(refresh_token)
        self.encrypted_access_token = encrypt_value(access_token) if access_token else ''
        self.token_expiry = expiry
        self.last_error = ''
        self.save(
            update_fields=[
                'encrypted_refresh_token',
                'encrypted_access_token',
                'token_expiry',
                'last_error',
            ]
        )

    def get_refresh_token(self) -> str:
        return decrypt_value(self.encrypted_refresh_token)

    def get_access_token(self) -> str:
        if not self.encrypted_access_token:
            return ''
        return decrypt_value(self.encrypted_access_token)

    def update_access_token(self, access_token: str, expiry):
        self.encrypted_access_token = encrypt_value(access_token) if access_token else ''
        self.token_expiry = expiry
        self.save(update_fields=['encrypted_access_token', 'token_expiry'])

    def disconnect(self):
        self.is_active = False
        
        try:
            refresh_token = self.get_refresh_token()
            if refresh_token:
                requests.post('https://oauth2.googleapis.com/revoke', params={'token': refresh_token}, timeout=5)
        except Exception as exc:
            logger.warning('Failed to revoke Google token during disconnect for %s: %s', self.sender_email, exc)

        self.encrypted_refresh_token = ''
        self.encrypted_access_token = ''
        self.token_expiry = None
        self.save(
            update_fields=[
                'is_active',
                'encrypted_refresh_token',
                'encrypted_access_token',
                'token_expiry',
            ]
        )

    @property
    def daily_send_limit(self) -> int:
        return getattr(settings, 'GMAIL_DAILY_SEND_LIMIT', DEFAULT_GMAIL_DAILY_SEND_LIMIT)

    @property
    def rate_limit_per_minute(self) -> int:
        return getattr(settings, 'GMAIL_RATE_LIMIT_PER_MINUTE', DEFAULT_GMAIL_RATE_LIMIT_PER_MINUTE)

    def _reset_daily_counter_if_needed(self):
        today = localdate()
        if self.daily_send_count_date != today:
            self.daily_send_count = 0
            self.daily_send_count_date = today
            self.save(update_fields=['daily_send_count', 'daily_send_count_date'])

    def remaining_daily_quota(self) -> int:
        self._reset_daily_counter_if_needed()
        return max(0, self.daily_send_limit - self.daily_send_count)

    def can_send(self, count: int = 1) -> bool:
        return self.remaining_daily_quota() >= count

    def record_send(self, count: int = 1):
        self._reset_daily_counter_if_needed()
        self.daily_send_count = models.F('daily_send_count') + count
        self.save(update_fields=['daily_send_count'])
        self.refresh_from_db(fields=['daily_send_count'])
        self._increment_rate_counter(count)

    def _rate_cache_key(self) -> str:
        minute_bucket = now().strftime('%Y%m%d%H%M')
        return f'gmail_rate:{self.pk}:{minute_bucket}'

    def _increment_rate_counter(self, count: int = 1):
        key = self._rate_cache_key()
        current = cache.get(key, 0)
        cache.set(key, current + count, timeout=120)

    def rate_limit_exceeded(self) -> bool:
        key = self._rate_cache_key()
        current = cache.get(key, 0)
        return current >= self.rate_limit_per_minute

    def seconds_until_rate_limit_reset(self) -> int:
        current = now()
        next_minute = (current + timedelta(minutes=1)).replace(second=0, microsecond=0)
        return max(1, int((next_minute - current).total_seconds()))

    def seconds_until_daily_reset(self) -> int:
        current_local = localtime()
        tomorrow_local = current_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return max(60, int((tomorrow_local - current_local).total_seconds()))

    def set_last_error(self, message: str):
        self.last_error = message[:2000]
        self.save(update_fields=['last_error'])
