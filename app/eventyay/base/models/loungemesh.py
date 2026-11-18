import secrets
import uuid

from django.db import models


def default_token():
    return f"lms_{secrets.token_urlsafe(32)}"


class LoungeMeshServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    active = models.BooleanField(default=True)
    url = models.URLField(max_length=300)
    api_secret = models.CharField(max_length=300, blank=True)
    cost = models.IntegerField(default=0)
    event_exclusive = models.ForeignKey(
        "Event", null=True, blank=True, on_delete=models.PROTECT
    )
    organizers = models.ManyToManyField(
        "Organizer", blank=True, related_name="loungemesh_servers"
    )
    events = models.ManyToManyField(
        "Event", blank=True, related_name="loungemesh_servers"
    )

    def __str__(self):
        return self.url
