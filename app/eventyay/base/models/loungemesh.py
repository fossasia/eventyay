import uuid

from django.db import models
from django.utils.crypto import get_random_string


def generate_opaque_token() -> str:
    return get_random_string(64)


class LoungeMeshAccessToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True, default=generate_opaque_token)
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='loungemesh_tokens')
    room = models.ForeignKey('Room', on_delete=models.CASCADE, related_name='loungemesh_tokens')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='loungemesh_tokens')
    is_moderator = models.BooleanField(default=False)
    display_name = models.CharField(max_length=300, blank=True)
    order_code = models.CharField(max_length=64, blank=True)
    expires = models.DateTimeField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires']),
        ]
