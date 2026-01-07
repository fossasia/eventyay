from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

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

    def get_queryset(self):
        room_id = self.kwargs.get('room_pk')
        if room_id:
            return StreamSchedule.objects.filter(
                room_id=room_id, room__event=self.event
            )
        return StreamSchedule.objects.filter(room__event=self.event)

    def perform_create(self, serializer):
        try:
            room_id = self.kwargs.get('room_pk')
            if room_id:
                room = Room.objects.get(pk=room_id, event=self.event)
                instance = serializer.save(room=room)
            else:
                instance = serializer.save()

            current_stream = instance.room.get_current_stream()
            if current_stream and current_stream.pk == instance.pk:
                async_to_sync(broadcast_stream_change)(
                    instance.room.pk, instance, reload=True
                )

            async_to_sync(notify_event_change)(self.event.id)
        except ValidationError as e:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            if hasattr(e, 'message_dict') and e.message_dict:
                error_dict = e.message_dict
            elif hasattr(e, 'messages') and e.messages:
                messages = (
                    list(e.messages)
                    if hasattr(e.messages, '__iter__')
                    and not isinstance(e.messages, str)
                    else [str(e.messages)]
                )
                error_dict = {'__all__': messages}
            else:
                error_dict = {'__all__': [str(e)]}

            raise DRFValidationError(error_dict)

    def perform_update(self, serializer):
        try:
            instance = serializer.save()
            current_stream = instance.room.get_current_stream()
            if current_stream and current_stream.pk == instance.pk:
                async_to_sync(broadcast_stream_change)(
                    instance.room.pk, instance, reload=True
                )

            async_to_sync(notify_event_change)(self.event.id)
        except ValidationError as e:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            if hasattr(e, 'message_dict') and e.message_dict:
                error_dict = e.message_dict
            elif hasattr(e, 'messages') and e.messages:
                messages = (
                    list(e.messages)
                    if hasattr(e.messages, '__iter__')
                    and not isinstance(e.messages, str)
                    else [str(e.messages)]
                )
                error_dict = {'__all__': messages}
            else:
                error_dict = {'__all__': [str(e)]}

            raise DRFValidationError(error_dict)

    def perform_destroy(self, instance):
        room_id = instance.room.pk
        was_current = (
            instance.room.get_current_stream()
            and instance.room.get_current_stream().pk == instance.pk
        )
        instance.delete()

        if was_current:
            new_current = Room.objects.get(pk=room_id).get_current_stream()
            async_to_sync(broadcast_stream_change)(room_id, new_current, reload=True)

        async_to_sync(notify_event_change)(self.event.id)
