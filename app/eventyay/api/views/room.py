import hashlib
from datetime import datetime

from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.utils.cache import patch_cache_control
from django.utils.http import http_date
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import exceptions, pagination, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from eventyay.api.documentation import build_search_docs
from eventyay.api.mixins import PretalxViewSetMixin, request_is_private
from eventyay.api.serializers.room import RoomOrgaSerializer, RoomSerializer
from eventyay.api.serializers.stream_schedule import StreamScheduleSerializer
from eventyay.api.throttles import EventyayUserRateThrottle, PublicStreamThrottle
from eventyay.base.exporters.room_broadcast import (
    VideoRoomBroadcastConfigurationExporter,
)
from eventyay.base.models.room import Room
from eventyay.base.services.room import (
    CURRENT_STREAM_HTTP_MAX_AGE,
    NEXT_STREAM_HTTP_MAX_AGE,
    get_cached_current_stream_data,
    get_cached_next_stream_data,
)


def stream_http_response(request, data, *, max_age):
    if data:
        etag = hashlib.md5(
            f'{data.get("id")}:{data.get("updated_at")}'.encode(),
            usedforsecurity=False,
        ).hexdigest()
        etag_header = f'"{etag}"'
        if_none_match = request.headers.get('If-None-Match', '')
        if etag_header in {part.strip() for part in if_none_match.split(',')}:
            response = Response(status=304)
        else:
            response = Response(data)
        response['ETag'] = etag_header
        updated = data.get('updated_at')
        if updated:
            try:
                stamp = datetime.fromisoformat(str(updated).replace('Z', '+00:00'))
                response['Last-Modified'] = http_date(stamp.timestamp())
            except ValueError:
                pass
    else:
        response = Response(status=404)

    if request_is_private(request):
        patch_cache_control(response, no_store=True)
    else:
        patch_cache_control(
            response,
            max_age=max_age,
            public=True,
            stale_while_revalidate=60,
        )
    return response


def current_stream_http_response(request, data):
    return stream_http_response(request, data, max_age=CURRENT_STREAM_HTTP_MAX_AGE)


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
            return self.event.rooms.with_has_linked_sessions().select_related("event")
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
        summary="Export Video Room Broadcast Configuration",
        parameters=[
            OpenApiParameter(
                "_format",
                str,
                OpenApiParameter.QUERY,
                enum=["xlsx", "default", "csv-excel", "semicolon"],
            )
        ],
        responses={200: bytes},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="export-broadcast-configuration",
    )
    def export_broadcast_configuration(self, request, **kwargs):
        if not (
            "can_change_event_settings" in request.eventpermset
            or "can_video_manage_rooms" in request.eventpermset
        ):
            raise PermissionDenied()

        export_format = request.query_params.get("_format", "xlsx")
        if export_format not in {"xlsx", "default", "csv-excel", "semicolon"}:
            return Response(
                {"_format": ["Invalid export format."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filename, content_type, content = VideoRoomBroadcastConfigurationExporter(
            self.event
        ).render({"_format": export_format})
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @extend_schema(
        summary="Get Current Stream",
        description="Returns the currently active stream schedule for this room, if any.",
        responses={200: StreamScheduleSerializer, 404: None},
    )
    @action(detail=True, methods=["get"], url_path="streams/current", throttle_classes=[PublicStreamThrottle, EventyayUserRateThrottle])
    def current_stream(self, request, pk=None, **kwargs):
        room = self.get_object()
        data = get_cached_current_stream_data(room)
        return current_stream_http_response(request, data)

    @extend_schema(
        summary="Get Next Stream",
        description="Returns the next upcoming stream schedule for this room, if any.",
        responses={200: StreamScheduleSerializer, 404: None},
    )
    @action(detail=True, methods=["get"], url_path="streams/next",
            throttle_classes=[PublicStreamThrottle, EventyayUserRateThrottle])
    def next_stream(self, request, pk=None, **kwargs):
        room = self.get_object()
        data = get_cached_next_stream_data(room)
        return stream_http_response(request, data, max_age=NEXT_STREAM_HTTP_MAX_AGE)
