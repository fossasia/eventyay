from rest_framework import serializers

from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.base.models.event import Event
from eventyay.base.models.room import Room


class RoomSerializer(I18nAwareModelSerializer):
    module_config = serializers.ListField(
        child=serializers.DictField(), required=False, default=[]
    )
    trait_grants = serializers.DictField(required=False, default={})
    has_linked_sessions = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            "id",
            "deleted",
            "trait_grants",
            "module_config",
            "name",
            "description",
            "sorting_priority",
            "pretalx_id",
            "schedule_data",
            "is_unscheduled",
            "has_linked_sessions",
            # TODO: picture
        ]

    def get_has_linked_sessions(self, obj):
        from django_scopes import scope
        with scope(event=obj.event):
            return obj.talks.filter(submission__isnull=False).exists()


class EventSerializer(serializers.ModelSerializer):
    config = serializers.DictField()
    trait_grants = serializers.DictField()
    roles = serializers.DictField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "config",
            "trait_grants",
            "roles",
            "domain",
        ]
