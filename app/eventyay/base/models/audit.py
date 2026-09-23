from django.db import models
from django.db.models import JSONField

from eventyay.base.operational_logging import emit_logged_action


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
            "user": self.user.serialize_public(),
            "type": self.type,
            "data": self.data,
        }
