from rest_framework import serializers

from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.base.models.event import Event
from eventyay.base.models.room import Room, NullSafeBooleanField


class RoomSerializer(I18nAwareModelSerializer):
    module_config = serializers.ListField(
        child=serializers.DictField(), required=False, default=[]
    )
    trait_grants = serializers.DictField(required=False, default={})
    deleted = NullSafeBooleanField(required=False, default=False)
    force_join = NullSafeBooleanField(required=False, default=False)
    hidden = NullSafeBooleanField(required=False, default=False)
    sidebar_hidden = NullSafeBooleanField(required=False, default=True)
    setup_complete = NullSafeBooleanField(required=False, default=False)

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
            "force_join",
            "setup_complete",
            "hidden",
            "sidebar_hidden",
            # TODO: picture
        ]


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
