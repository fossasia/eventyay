from rest_framework import viewsets
from eventyay.api.mixins import PretalxViewSetMixin
from eventyay.api.serializers.event_message import EventMessageSerializer
from eventyay.base.models.event_message import EventMessage


class EventMessageViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    serializer_class = EventMessageSerializer
    endpoint = "messages"

    def get_queryset(self):
        return EventMessage.objects.filter(event=self.event).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(event=self.event)
