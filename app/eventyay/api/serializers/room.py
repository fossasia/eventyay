from rest_framework import serializers
from rest_framework.serializers import UUIDField

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.serializers.availability import (
    AvailabilitiesMixin,
    AvailabilitySerializer,
)
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.base.models.room import Room


@register_serializer(versions=CURRENT_VERSIONS)
class RoomSerializer(AvailabilitiesMixin, PretalxSerializer):
    uuid = UUIDField(
        help_text="The uuid field is equal the the guid field if a guid has been set. Otherwise, it will contain a computed (stable) UUID.",
        read_only=True,
    )
    has_linked_sessions = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = (
            "id",
            "name",
            "description",
            "uuid",
            "guid",
            "capacity",
            "position",
            "is_unscheduled",
            "has_linked_sessions",
        )

    def get_has_linked_sessions(self, obj):
        from django_scopes import scope
        with scope(event=obj.event):
            return obj.talks.filter(submission__isnull=False).exists()


@register_serializer(versions=CURRENT_VERSIONS)
class RoomOrgaSerializer(RoomSerializer):
    availabilities = AvailabilitySerializer(many=True, required=False)

    def create(self, validated_data):
        availabilities_data = validated_data.pop("availabilities", None)
        validated_data["event"] = getattr(self.context.get("request"), "event", None)
        room = super().create(validated_data)
        if availabilities_data is not None:
            self._handle_availabilities(room, availabilities_data, field="room")
        return room

    def update(self, instance, validated_data):
        availabilities_data = validated_data.pop("availabilities", None)
        room = super().update(instance, validated_data)
        if availabilities_data is not None:
            self._handle_availabilities(room, availabilities_data, field="room")
        return room

    class Meta:
        model = Room
        fields = RoomSerializer.Meta.fields + ("speaker_info", "availabilities")
