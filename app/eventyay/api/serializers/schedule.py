from datetime import timedelta

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django_scopes import scope
from drf_spectacular.utils import extend_schema_field
from rest_flex_fields.serializers import FlexFieldsSerializerMixin
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import (
    CharField,
    DateTimeField,
    SerializerMethodField,
    SlugRelatedField,
)

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.base.models.schedule import Schedule
from eventyay.base.models.slot import TalkSlot
from eventyay.talk_rules.tracks import apply_track_limit_to_slots, user_has_track_limits


@register_serializer()
class ScheduleListSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    version = CharField(source='version_with_fallback')

    class Meta:
        model = Schedule
        fields = ['id', 'version', 'published']


@register_serializer(versions=CURRENT_VERSIONS)
class ScheduleSerializer(ScheduleListSerializer):
    slots = SerializerMethodField()

    @extend_schema_field(list[int])
    def get_slots(self, obj):
        only_visible_slots = self.context.get('only_visible_slots', True)
        if only_visible_slots and not obj.version:
            # This should never happen, but better safe than sorry.
            return []
        qs = obj.talks.all()
        if only_visible_slots:
            qs = qs.filter(is_visible=True).exclude(room__deleted=True)
        request = self.context.get('request')
        if request and obj.event and user_has_track_limits(obj.event, request.user):
            qs = apply_track_limit_to_slots(qs, obj.event, request.user)
        if serializer := self.get_extra_flex_field('slots', qs):
            return serializer.data
        return qs.values_list('pk', flat=True)

    class Meta(ScheduleListSerializer.Meta):
        fields = ScheduleListSerializer.Meta.fields + ['comment', 'slots']
        extra_expandable_fields = {
            'slots': (
                'eventyay.api.serializers.schedule.TalkSlotSerializer',
                {'read_only': True, 'many': True, 'omit': ('schedule',)},
            )
        }


@register_serializer(versions=CURRENT_VERSIONS)
class ScheduleReleaseSerializer(PretalxSerializer):
    version = serializers.CharField(required=True)
    comment = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Schedule
        fields = ('version', 'comment')

    def validate_version(self, value):
        """Reject reserved or previously used version names before schedule release."""
        value = value.strip()
        if value.lower() in ('wip', 'latest'):
            raise ValidationError(_('This schedule version is reserved. Please choose a different name.'))
        event = self.context['request'].event
        if event.schedules.filter(version__iexact=value).exists():
            raise ValidationError(
                _("A schedule with the version '%(version)s' already exists for this event.") % {'version': value}
            )
        return value


@register_serializer(versions=CURRENT_VERSIONS)
class TalkSlotSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    submission = SlugRelatedField(slug_field='code', read_only=True)
    end = DateTimeField(source='local_end')

    @transaction.atomic
    def update(self, instance, validated_data):
        """Coordinate slot edits with release/reset and reject stale draft targets."""
        event = instance.event
        with scope(event=event):
            type(event).objects.select_for_update(no_key=True).get(pk=event.pk)
            try:
                instance = TalkSlot.objects.select_related('schedule', 'submission__submission_type').get(
                    pk=instance.pk,
                )
            except TalkSlot.DoesNotExist as exc:
                raise ValidationError('The draft schedule changed. Reload it before editing this slot.') from exc
            if instance.schedule.version:
                raise ValidationError('Released schedule slots cannot be edited. Reload the draft schedule.')
            if 'local_end' in validated_data:
                validated_data['end'] = validated_data.pop('local_end')
            if 'start' in validated_data and instance.submission_id:
                start = validated_data['start']
                validated_data['end'] = (
                    start + timedelta(minutes=instance.submission.get_duration()) if start else None
                )
            return super().update(instance, validated_data)

    class Meta:
        model = TalkSlot
        fields = [
            'id',
            'room',
            'start',
            'end',
            'submission',
            'schedule',
            'description',
            'duration',
        ]
        read_only_fields = ['submission', 'schedule']
        expandable_fields = {
            'submission': (
                'eventyay.api.serializers.submission.SubmissionSerializer',
                {'read_only': True, 'omit': ('slots',)},
            ),
            'schedule': (
                'eventyay.api.serializers.schedule.ScheduleSerializer',
                {'read_only': True, 'omit': ('slots', 'speakers')},
            ),
            'room': (
                'eventyay.api.serializers.room.RoomSerializer',
                {'read_only': True},
            ),
        }


@register_serializer(versions=CURRENT_VERSIONS)
class TalkSlotOrgaSerializer(TalkSlotSerializer):
    class Meta(TalkSlotSerializer.Meta):
        fields = TalkSlotSerializer.Meta.fields + ['is_visible']
        read_only_fields = TalkSlotSerializer.Meta.read_only_fields + ['is_visible']
        expandable_fields = TalkSlotSerializer.Meta.expandable_fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        from django.core.exceptions import ValidationError as DjangoValidationError

        from eventyay.base.models.room import validate_talk_slot_room_from_attrs

        try:
            validate_talk_slot_room_from_attrs(attrs, self.instance)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
        return attrs

    def validate_end(self, value):
        if self.instance and self.instance.submission:
            raise ValidationError(
                'End can only be edited if there is no submission associated with the slot. '
                'Otherwise, update the submission duration.'
            )
        return value

    def validate_description(self, value):
        if self.instance and self.instance.submission:
            raise ValidationError(
                'Description can only be edited if there is no submission associated with the slot. '
                'Otherwise, update the submission abstract.'
            )
        return value
