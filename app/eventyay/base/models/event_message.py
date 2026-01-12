import uuid
from django.conf import settings
from django.db import models


class EventMessage(models.Model):
    class States(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"

    class Audiences(models.TextChoices):
        ATTENDEES = "attendees", "Attendees"
        SPEAKERS = "speakers", "Speakers"
        STAFF = "staff", "Staff"
        ALL = "all", "All"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    event = models.ForeignKey(
        "base.Event",
        on_delete=models.CASCADE,
        related_name="messages",
    )

    subject = models.CharField(max_length=255)
    body_text = models.TextField()
    body_html = models.TextField(blank=True)

    audience = models.CharField(max_length=32, choices=Audiences.choices)
    state = models.CharField(
        max_length=16, choices=States.choices, default=States.DRAFT
    )

    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["state"]),
            models.Index(fields=["scheduled_at"]),
            models.Index(fields=["event","-created_at"]),
        ]


class EventMessageDelivery(models.Model):
    class States(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(
        EventMessage,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="event_message_deliveries",
    )
    email = models.EmailField()

    state = models.CharField(
        max_length=16, choices=States.choices, default=States.PENDING
    )
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [
            ("message", "email"),
        ]
        indexes = [
            models.Index(fields=["message"]),
            models.Index(fields=["state"]),
        ]

