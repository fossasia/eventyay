from contextlib import suppress

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.response import Response

from eventyay.api.documentation import build_search_docs
from eventyay.api.mixins import PretalxViewSetMixin
from eventyay.api.serializers.stream_schedule import StreamScheduleSerializer
from eventyay.base.models.room import Room
from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.services.event import notify_event_change
from eventyay.base.services.room import broadcast_stream_change


@extend_schema_view(
    list=extend_schema(
        summary='List Stream Schedules', parameters=[build_search_docs('title')]
    ),
    retrieve=extend_schema(summary='Show Stream Schedule'),
    create=extend_schema(
        summary='Create Stream Schedule',
        request=StreamScheduleSerializer,
        responses={201: StreamScheduleSerializer},
    ),
    update=extend_schema(
        summary='Update Stream Schedule',
        request=StreamScheduleSerializer,
        responses={200: StreamScheduleSerializer},
    ),
    partial_update=extend_schema(
        summary='Update Stream Schedule (Partial Update)',
        request=StreamScheduleSerializer,
        responses={200: StreamScheduleSerializer},
    ),
    destroy=extend_schema(summary='Delete Stream Schedule'),
)
class StreamScheduleViewSet(PretalxViewSetMixin, viewsets.ModelViewSet):
    queryset = StreamSchedule.objects.none()
    serializer_class = StreamScheduleSerializer
    endpoint = 'stream_schedules'
    search_fields = ('title',)

    def dispatch(self, request, *args, **kwargs):
        if settings.DEBUG and request.META.get('HTTP_HOST', '').startswith(
            ('localhost', '127.0.0.1')
        ):
            request._dont_enforce_csrf_checks = True
        return super().dispatch(request, *args, **kwargs)

    def initial(self, request, *args, **kwargs):
        """Ensure request.event is set from the room if not already present."""
        super().initial(request, *args, **kwargs)
        room_id = self.kwargs.get('room_pk')
        if room_id and (not hasattr(request, 'event') or not request.event):
            with suppress(Room.DoesNotExist):
                room = Room.objects.select_related('event', 'event__organizer').get(
                    pk=room_id
                )
                request.event = room.event
                request.organizer = room.event.organizer

    def get_room(self):
        room_id = self.kwargs.get('room_pk')
        if not room_id:
            return None
        try:
            if self.event:
                return Room.objects.get(pk=room_id, event=self.event)
            return Room.objects.select_related('event').get(pk=room_id)
        except Room.DoesNotExist:
            return None

    def get_serializer_context(self):
        context = super().get_serializer_context()
        room = self.get_room()
        if room:
            context['room'] = room
        return context

    def get_queryset(self):
        room_id = self.kwargs.get('room_pk')
        if not self.event:
            if room_id:
                try:
                    room = Room.objects.select_related('event').get(pk=room_id)
                    return StreamSchedule.objects.filter(room=room)
                except Room.DoesNotExist:
                    return StreamSchedule.objects.none()
            return StreamSchedule.objects.none()
        if room_id:
            return StreamSchedule.objects.filter(
                room_id=room_id, room__event=self.event
            )
        return StreamSchedule.objects.filter(room__event=self.event)

    def create(self, request, *args, **kwargs):
        room = self.get_room()
        if not room:
            return Response({'room': ['Room not found.']}, status=400)

        serializer = self.get_serializer(data=request.data)
        serializer.context['room'] = room

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            previous_stream = room.get_current_stream()
            instance = serializer.save(room=room)
            current_stream = instance.room.get_current_stream()
            if previous_stream != current_stream:
                async_to_sync(broadcast_stream_change)(
                    instance.room.pk, current_stream, reload=True
                )
            event_id = self.event.id if self.event else instance.room.event_id
            async_to_sync(notify_event_change)(event_id)
            return Response(StreamScheduleSerializer(instance).data, status=201)
        except ValidationError as e:
            if hasattr(e, 'message_dict') and e.message_dict:
                error_dict = e.message_dict
            elif hasattr(e, 'messages') and e.messages:
                error_dict = {'__all__': list(e.messages)}
            else:
                error_dict = {'__all__': [str(e)]}
            return Response(error_dict, status=400)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if 'room' not in serializer.context or serializer.context['room'] is None:
            serializer.context['room'] = instance.room
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            previous_stream = instance.room.get_current_stream()
            instance = serializer.save()
            current_stream = instance.room.get_current_stream()
            if previous_stream != current_stream:
                async_to_sync(broadcast_stream_change)(
                    instance.room.pk, current_stream, reload=True
                )
            event_id = self.event.id if self.event else instance.room.event_id
            async_to_sync(notify_event_change)(event_id)
            return Response(StreamScheduleSerializer(instance).data)
        except ValidationError as e:
            if hasattr(e, 'message_dict') and e.message_dict:
                error_dict = e.message_dict
            elif hasattr(e, 'messages') and e.messages:
                error_dict = {'__all__': list(e.messages)}
            else:
                error_dict = {'__all__': [str(e)]}
            return Response(error_dict, status=400)

    def perform_destroy(self, instance):
        room_id = instance.room.pk
        current_stream = instance.room.get_current_stream()
        was_current = current_stream and current_stream.pk == instance.pk
        instance.delete()
        room = None
        if was_current:
            room = Room.objects.get(pk=room_id)
            new_current = room.get_current_stream()
            async_to_sync(broadcast_stream_change)(room_id, new_current, reload=True)
        if self.event:
            event_id = self.event.id
        else:
            if room is None:
                room = Room.objects.get(pk=room_id)
            event_id = room.event_id
        async_to_sync(notify_event_change)(event_id)
