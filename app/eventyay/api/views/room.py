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
    def current_stream(self, request, pk=None, **kwargs):
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
    def next_stream(self, request, pk=None, **kwargs):
        room = self.get_object()
        next_stream = room.get_next_stream()
        if next_stream:
            serializer = StreamScheduleSerializer(next_stream)
            return Response(serializer.data)
        return Response(status=404)
