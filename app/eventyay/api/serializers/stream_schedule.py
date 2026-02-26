from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_scopes import scope
from rest_framework import serializers

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.base.models.slot import TalkSlot
from eventyay.base.models.stream_schedule import StreamSchedule


@register_serializer(versions=CURRENT_VERSIONS)
class StreamScheduleSerializer(PretalxSerializer):
    class Meta:
        model = StreamSchedule
        fields = (
            'id',
            'room',
            'title',
            'url',
            'start_time',
            'end_time',
            'stream_type',
            'config',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('room', 'created_at', 'updated_at')

    def validate(self, data):
        data = super().validate(data)

        start_time = data.get('start_time')
        end_time = data.get('end_time')
        now = timezone.now()

        if self.instance:
            orig_start_time = self.instance.start_time
            start_time = start_time or orig_start_time
            end_time = end_time or self.instance.end_time
        else:
            orig_start_time = None

        if not self.instance and start_time and start_time < now:
            raise serializers.ValidationError(
                {'start_time': _('Start time cannot be in the past.')}
            )

        if (
            self.instance
            and 'start_time' in getattr(self, 'initial_data', {})
            and start_time
            and start_time < now
            and orig_start_time
            and orig_start_time >= now
        ):
            raise serializers.ValidationError(
                {'start_time': _('Start time cannot be in the past.')}
            )

        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError(
                {'end_time': _('End time must be after start time.')}
            )

        self._validate_coincides_with_session(
            room=self._get_room(), start_time=start_time, end_time=end_time
        )
        return self._validate_overlap(data)

    def _get_room(self):
        if self.instance:
            return self.instance.room

        return self.context.get('room')

    def _validate_coincides_with_session(self, *, room, start_time, end_time):
        if not (room and start_time and end_time):
            return

        with scope(event=room.event):
            match_exists = TalkSlot.objects.filter(
                schedule__event=room.event,
                room=room,
                submission__isnull=False,
                is_visible=True,
                start__lt=end_time,
                end__gt=start_time,
            ).exists()

        if not match_exists:
            raise serializers.ValidationError(
                {
                    '__all__': [
                        _(
                            'Stream schedules must include at least one scheduled session in this room.'
                        )
                    ]
                }
            )

    def _validate_overlap(self, data):
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if self.instance:
            start_time = start_time or self.instance.start_time
            end_time = end_time or self.instance.end_time

        room = self._get_room()

        if room and start_time and end_time:
            with scope(event=room.event):
                overlapping = StreamSchedule.objects.filter(
                    room=room, start_time__lt=end_time, end_time__gt=start_time
                )
                if self.instance:
                    overlapping = overlapping.exclude(pk=self.instance.pk)

                if overlapping.exists():
                    raise serializers.ValidationError(
                        {
                            '__all__': [
                                _(
                                    'This stream schedule overlaps with an existing schedule for this room. '
                                    'Please adjust the time range.'
                                )
                            ]
                        }
                    )

        return data

    def create(self, validated_data):
        instance = StreamSchedule(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
