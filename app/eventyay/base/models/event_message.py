import uuid
from django.db import models


class EventMessage(models.Model):
    class States(models.TextChoices):
        DRAFT = "draft"
        QUEUED = "queued"
        SENDING = "sending"
        SENT = "sent"

    class Audiences(models.TextChoices):
        ATTENDEES = "attendees"
        SPEAKERS = "speakers"
        STAFF = "staff"
        ALL = "all"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    event = models.ForeignKey(
        "Event",
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


class EventMessageDelivery(models.Model):
    class States(models.TextChoices):
        PENDING = "pending"
        SENT = "sent"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(
        EventMessage,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )

    user = models.ForeignKey(
        "User",
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
