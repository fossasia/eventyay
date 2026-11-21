import copy

from django.db import models
from django.db.models import JSONField

from eventyay.base.operational_logging import emit_logged_action

SENSITIVE_EVENT_CONFIG_KEYS = ("password", "secret", "api_key")
PROVIDER_DEFAULT_KEYS = ("bbb_defaults", "jitsi_defaults", "janus_defaults", "zoom_defaults")


def mask_event_config_secrets(event_config):
    """Return a copy of a serialized event config with secret settings masked for audit logs."""
    if not isinstance(event_config, dict):
        return event_config
    masked = copy.deepcopy(event_config)
    for key, value in list(masked.items()):
        if isinstance(value, str) and value and any(s in key for s in SENSITIVE_EVENT_CONFIG_KEYS):
            masked[key] = "********"
    for provider_key in PROVIDER_DEFAULT_KEYS:
        provider_cfg = masked.get(provider_key)
        if not isinstance(provider_cfg, dict):
            continue
        for key, value in list(provider_cfg.items()):
            if isinstance(value, str) and value and any(s in key for s in SENSITIVE_EVENT_CONFIG_KEYS):
                provider_cfg[key] = "********"
    return masked


def mask_audit_data(audit_type, data):
    if audit_type == "event.updated" and isinstance(data, dict):
        masked = dict(data)
        if "old" in masked:
            masked["old"] = mask_event_config_secrets(masked["old"])
        if "new" in masked:
            masked["new"] = mask_event_config_secrets(masked["new"])
        return masked
    return data


class AuditLog(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )
    event = models.ForeignKey(
        "Event",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="audits",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    type = models.CharField(max_length=255)
    data = JSONField()

    class Meta:
        indexes = [
            models.Index(fields=["event", "-timestamp", "-id"], name="base_auditl_event_t_desc_idx"),
        ]

    def save(self, *args, **kwargs):
        created = self._state.adding
        super().save(*args, **kwargs)
        if not created:
            return
        object_id = None
        payload = self.data
        if isinstance(payload, dict):
            raw = payload.get('object')
            if isinstance(raw, (int, str)):
                object_id = raw
        try:
            emit_logged_action(
                self.type,
                event_id=self.event_id,
                user_id=self.user_id,
                object_id=object_id,
                model='AuditLog',
            )
        except Exception:
            pass

    def serialize_public(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user": self.user.serialize_public() if self.user else None,
            "type": self.type,
            "data": mask_audit_data(self.type, self.data),
        }
