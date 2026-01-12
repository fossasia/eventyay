from rest_framework import serializers
from eventyay.base.models.event_message import EventMessage


class EventMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventMessage
        fields = (
            "id",
            "event",
            "subject",
            "body_text",
            "body_html",
            "audience",
            "state",
            "scheduled_at",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "state")
