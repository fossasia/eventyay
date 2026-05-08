from asgiref.sync import async_to_sync
from django.db import transaction
from django.db.models import Max
from rest_framework import viewsets

from eventyay.api.auth.api_auth import (
    ApiAccessRequiredPermission,
    RoomPermissions,
)
from eventyay.api.serializers.rooms import RoomSerializer
from eventyay.base.models import Channel
from eventyay.base.models.room import Room
from eventyay.base.services.event import notify_event_change
from eventyay.base.services.room import normalize_after_priority_change


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.none()
    serializer_class = RoomSerializer
    permission_classes = [ApiAccessRequiredPermission & RoomPermissions]

    def get_queryset(self):
        return self.request.event.rooms.with_permission(
            traits=self.request.auth.get("traits"), event=self.request.event
        )

    def perform_create(self, serializer):
        event = self.request.event
        provided_priority = serializer.validated_data.get("sorting_priority")
        if provided_priority is None or event.rooms.filter(
            deleted=False, sorting_priority=provided_priority
        ).exists():
            max_priority = (
                event.rooms.filter(deleted=False).aggregate(m=Max("sorting_priority"))["m"] or 0
            )
            serializer.validated_data["sorting_priority"] = max_priority + 1
        if serializer.validated_data.get("position") is None:
            serializer.validated_data["position"] = serializer.validated_data["sorting_priority"] - 1
        serializer.save(event=event)
        for m in serializer.instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.get_or_create(
                    room=serializer.instance, event=self.request.event
                )
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(self.request.event.id)
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        if "sorting_priority" in self.request.data:
            normalize_after_priority_change(
                self.request.event,
                serializer.instance.id,
                serializer.instance.sorting_priority,
            )
            serializer.instance.refresh_from_db()
        for m in serializer.instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.get_or_create(
                    room=serializer.instance, event=self.request.event
                )
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(self.request.event.id)
        )

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        for m in instance.module_config:
            if m["type"] == "chat.native":
                Channel.objects.filter(room=instance, event=self.request.event).delete()
        transaction.on_commit(  # pragma: no cover
            lambda: async_to_sync(notify_event_change)(self.request.event.id)
        )
