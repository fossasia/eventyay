from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import exceptions, pagination, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from eventyay.api.documentation import build_search_docs
from eventyay.api.mixins import PretalxViewSetMixin
from eventyay.api.serializers.room import RoomOrgaSerializer, RoomSerializer
from eventyay.api.serializers.stream_schedule import StreamScheduleSerializer
from eventyay.base.models.room import Room
from eventyay.base.models.stream_schedule import StreamSchedule


class RoomPagination(pagination.LimitOffsetPagination):
    default_limit = 100


@extend_schema_view(
    list=extend_schema(summary="List Rooms", parameters=[build_search_docs("name")]),
    retrieve=extend_schema(summary="Show Rooms"),
    create=extend_schema(
        summary="Create Rooms",
        request=RoomOrgaSerializer,
        responses={201: RoomOrgaSerializer},
    ),
    update=extend_schema(
        summary="Update Rooms",
        request=RoomOrgaSerializer,
        responses={200: RoomOrgaSerializer},
    ),
    partial_update=extend_schema(
        summary="Update Rooms (Partial Update)",
        request=RoomOrgaSerializer,
        responses={200: RoomOrgaSerializer},
    ),
    destroy=extend_schema(summary="Delete Rooms"),
)
class RoomViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    queryset = Room.objects.none()
    serializer_class = RoomSerializer
    pagination_class = RoomPagination
    endpoint = "rooms"
    search_fields = ("name",)

    def get_queryset(self):
        if self.event:
            return self.event.rooms.all().select_related("event")
        return Room.objects.none()

    def get_unversioned_serializer_class(self):
        if self.request.method not in SAFE_METHODS or self.has_perm("update"):
            return RoomOrgaSerializer
        return RoomSerializer

    def perform_destroy(self, instance):
        try:
            with transaction.atomic():
                instance.logged_actions().delete()
                return super().perform_destroy(instance)
        except ProtectedError:
            raise exceptions.ValidationError(
                "You cannot delete a room that has been used in the schedule."
            )

    @extend_schema(
        summary="Get Current Stream",
        description="Returns the currently active stream schedule for this room, if any.",
        responses={200: StreamScheduleSerializer, 404: None},
    )
    @action(detail=True, methods=["get"], url_path="streams/current")
    def current_stream(self, request, pk=None):
        room = self.get_object()
        current = room.get_current_stream()
        if current:
            serializer = StreamScheduleSerializer(current)
            return Response(serializer.data)
        return Response(status=404)

    @extend_schema(
        summary="Get Next Stream",
        description="Returns the next upcoming stream schedule for this room, if any.",
        responses={200: StreamScheduleSerializer, 404: None},
    )
    @action(detail=True, methods=["get"], url_path="streams/next")
    def next_stream(self, request, pk=None):
        room = self.get_object()
        next_stream = room.get_next_stream()
        if next_stream:
            serializer = StreamScheduleSerializer(next_stream)
            return Response(serializer.data)
        return Response(status=404)

    @extend_schema(
        summary="List Stream Schedules",
        responses={200: StreamScheduleSerializer(many=True)},
    )
    @extend_schema(
        methods=["post"],
        summary="Create Stream Schedule",
        request=StreamScheduleSerializer,
        responses={201: StreamScheduleSerializer},
    )
    @action(detail=True, methods=["get", "post"], url_path="stream-schedules")
    def stream_schedules(self, request, pk=None, **kwargs):
        if settings.DEBUG and request.META.get("HTTP_HOST", "").startswith(
            ("localhost", "127.0.0.1")
        ):
            setattr(request, "_dont_enforce_csrf_checks", True)
        try:
            room = Room.objects.select_related("event", "event__organizer").get(pk=pk)
        except Room.DoesNotExist:
            return Response({"detail": "Room not found"}, status=404)
        if not hasattr(request, "event") or not request.event:
            request.event = room.event
            request.organizer = room.event.organizer

        if request.method == "GET":
            schedules = StreamSchedule.objects.filter(room=room).order_by("start_time")
            serializer = StreamScheduleSerializer(schedules, many=True)
            return Response(serializer.data)
        elif request.method == "POST":
            from asgiref.sync import async_to_sync
            from eventyay.base.services.room import broadcast_stream_change
            from eventyay.base.services.event import notify_event_change

            event = room.event
            serializer = StreamScheduleSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    instance = serializer.save(room=room)
                    current_stream = instance.room.get_current_stream()
                    if current_stream and current_stream.pk == instance.pk:
                        async_to_sync(broadcast_stream_change)(
                            instance.room.pk, instance, reload=True
                        )
                    async_to_sync(notify_event_change)(event.id)
                    return Response(StreamScheduleSerializer(instance).data, status=201)
                except ValidationError as e:
                    if hasattr(e, "message_dict") and e.message_dict:
                        error_dict = e.message_dict
                    elif hasattr(e, "messages") and e.messages:
                        error_dict = {"__all__": list(e.messages)}
                    else:
                        error_dict = {"__all__": [str(e)]}
                    return Response(error_dict, status=400)
            return Response(serializer.errors, status=400)
