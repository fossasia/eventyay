from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_scopes import scope
from rest_framework import serializers

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.base.models.slot import TalkSlot
from eventyay.base.models.stream_schedule import StreamSchedule


class StageStreamScheduleSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    title = serializers.CharField(required=False, allow_blank=True, default='')
    url = serializers.URLField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    stream_type = serializers.ChoiceField(
        choices=StreamSchedule._meta.get_field('stream_type').choices
    )
    config = serializers.DictField(required=False, default=dict)


class StageStreamConfigurationSerializer(serializers.Serializer):
    module_config = serializers.ListField(child=serializers.DictField())
    schedules = StageStreamScheduleSerializer(many=True)

    def validate(self, data):
        data = super().validate(data)
        room = self.context['room']
        schedules = data['schedules']
        schedule_errors = [{} for schedule in schedules]

        stage_modules = [
            module
            for module in data['module_config']
            if module.get('type')
            in {
                'livestream.native',
                'livestream.youtube',
                'livestream.iframe',
            }
        ]
        if len(stage_modules) != 1:
            raise serializers.ValidationError(
                {'module_config': _('A stage must contain exactly one stream module.')}
            )

        stage_module = stage_modules[0]
        stage_config = stage_module.get('config')
        if not isinstance(stage_config, dict):
            raise serializers.ValidationError(
                {'module_config': _('The stream module configuration is invalid.')}
            )

        playback_mode = stage_config.get('playback_mode')
        if schedules and playback_mode != 'schedule_driven':
            raise serializers.ValidationError(
                {
                    'module_config': _(
                        'Scheduled streams require schedule-driven playback.'
                    )
                }
            )
        if not schedules and playback_mode != 'always_on':
            raise serializers.ValidationError(
                {'schedules': _('Schedule-driven playback requires a stream schedule.')}
            )
        if not schedules:
            self.validate_default_stream(stage_module)

        schedule_ids = [schedule['id'] for schedule in schedules if 'id' in schedule]
        if len(schedule_ids) != len(set(schedule_ids)):
            raise serializers.ValidationError(
                {'schedules': _('A stream schedule cannot be included more than once.')}
            )

        with scope(event=room.event):
            existing_schedules = {
                schedule.pk: schedule
                for schedule in StreamSchedule.objects.filter(
                    room=room, pk__in=schedule_ids
                )
            }
        now = timezone.now()
        for index, schedule in enumerate(schedules):
            schedule_id = schedule.get('id')
            existing = existing_schedules.get(schedule_id) if schedule_id else None
            if schedule_id and existing is None:
                schedule_errors[index]['id'] = [_('Stream schedule not found.')]
            if schedule['end_time'] <= schedule['start_time']:
                schedule_errors[index]['end_time'] = [
                    _('End time must be after start time.')
                ]
            if existing is None and schedule['start_time'] < now:
                schedule_errors[index]['start_time'] = [
                    _('Start time cannot be in the past.')
                ]
            elif (
                existing is not None
                and existing.start_time >= now
                and schedule['start_time'] < now
            ):
                schedule_errors[index]['start_time'] = [
                    _('Start time cannot be in the past.')
                ]

        ordered = sorted(enumerate(schedules), key=lambda item: item[1]['start_time'])
        for position, (index, schedule) in enumerate(ordered[1:], start=1):
            previous_index, previous = ordered[position - 1]
            if schedule['start_time'] < previous['end_time']:
                message = _(
                    'This stream schedule overlaps with another stream for this room. '
                    'Please adjust the time range.'
                )
                schedule_errors[index].setdefault('__all__', []).append(message)
                schedule_errors[previous_index].setdefault('__all__', []).append(
                    message
                )

        if room.event.talks_published:
            with scope(event=room.event):
                for index, schedule in enumerate(schedules):
                    match_exists = TalkSlot.objects.filter(
                        schedule__event=room.event,
                        room=room,
                        submission__isnull=False,
                        is_visible=True,
                        start__lt=schedule['end_time'],
                        end__gt=schedule['start_time'],
                    ).exists()
                    if not match_exists:
                        schedule_errors[index].setdefault('__all__', []).append(
                            _(
                                'Stream schedules must include at least one scheduled session in this room.'
                            )
                        )

        if any(schedule_errors):
            raise serializers.ValidationError({'schedules': schedule_errors})

        data['existing_schedules'] = existing_schedules
        return data

    def validate_default_stream(self, stage_module):
        config = stage_module['config']
        module_type = stage_module['type']
        field_by_module = {
            'livestream.native': 'hls_url',
            'livestream.youtube': 'ytid',
            'livestream.iframe': 'url',
        }
        field = field_by_module[module_type]
        value = config.get(field)
        if not isinstance(value, str) or not value.strip():
            raise serializers.ValidationError(
                {'module_config': _('Stream URL or input is required.')}
            )
        if module_type in {'livestream.native', 'livestream.iframe'}:
            validator = serializers.URLField()
            try:
                validator.run_validation(value)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError(
                    {'module_config': _('Enter a valid stream URL.')}
                ) from exc


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

        # Allow creating stream schedules while the event schedule is still being drafted.
        # Enforce the overlap requirement once talks are published.
        if not room.event.talks_published:
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
