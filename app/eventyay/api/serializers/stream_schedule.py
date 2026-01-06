from rest_framework import serializers

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
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
        read_only_fields = ('created_at', 'updated_at')

