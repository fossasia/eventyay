import uuid

from django.db import models


class JanusServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    url = models.CharField(max_length=200)
    room_create_key = models.CharField(max_length=300)
    events_exclusive = models.ManyToManyField(
        "Event", blank=True
    )
