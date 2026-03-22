from django.db import models
from django.conf import settings

try:
    from django.db.models import JSONField
except ImportError:
    from django.contrib.postgres.fields import JSONField



class KeyTypes(models.TextChoices):
    FIDO2 = 'FIDO2', "FIDO2 Security Device"
    TOTP = 'TOTP', "TOTP Authenticator"


# keys that can only be used on one domain
DOMAIN_KEYS = (KeyTypes.FIDO2)


class UserKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name='multifactor_keys')
    name = models.CharField(max_length=30, help_text="Easy to remember name to distinguish from any other keys of this sort you own.", blank=True, null=True)
    properties = JSONField(null=True)
    key_type = models.CharField(max_length=25, choices=KeyTypes.choices)
    enabled = models.BooleanField(default=True)

    added_on = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField(null=True, default=None, blank=True)
    last_used = models.DateTimeField(null=True, default=None, blank=True)

    def __str__(self):
        if self.name:
            return f"{self.get_key_type_display()}, aka \"{self.name}\" for {self.user}"
        return f"{self.get_key_type_display()} for {self.user}"

    def display_name(self):
        if self.name:
            return f"{self.name} ({self.key_type})"
        return self.get_key_type_display()

    @property
    def device(self):
        if self.key_type == KeyTypes.FIDO2:
            return self.properties.get("type", "----")
        return ""

    @property
    def auth_url(self):
        from .common import method_url
        return method_url(self.key_type)


class DisabledFallback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name='+')
    fallback = models.CharField(max_length=50)
