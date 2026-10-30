from pathlib import Path

from django.db import transaction
from rest_flex_fields.serializers import FlexFieldsSerializerMixin

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.serializers.fields import UploadedFileField
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.base.models.information import SpeakerInformation
from eventyay.base.models.track import Track
from eventyay.base.models.type import SubmissionType


@register_serializer(versions=CURRENT_VERSIONS)
class SpeakerInformationSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    resource = UploadedFileField(required=False, allow_null=True)

    class Meta:
        model = SpeakerInformation
        fields = (
            "id",
            "target_group",
            "title",
            "text",
            "resource",
            "limit_tracks",
            "limit_types",
        )
        expandable_fields = {
            "limit_tracks": (
                "eventyay.api.serializers.submission.TrackSerializer",
                {"many": True, "read_only": True},
            ),
            "limit_types": (
                "eventyay.api.serializers.submission.SubmissionTypeSerializer",
                {"many": True, "read_only": True},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.event:
            self.fields["limit_tracks"].queryset = self.event.tracks.all()
            self.fields["limit_types"].queryset = self.event.submission_types.all()
        else:
            self.fields["limit_tracks"].queryset = Track.objects.none()
            self.fields["limit_types"].queryset = SubmissionType.objects.none()

    def create(self, validated_data):
        validated_data["event"] = self.event
        resource = validated_data.pop("resource", None)
        with transaction.atomic():
            instance = super().create(validated_data)
            if resource:
                instance.resource.save(Path(resource.name).name, resource, save=False)
                new_saved_name = instance.resource.name
                try:
                    instance.save(update_fields=("resource",))
                except Exception:
                    if new_saved_name:
                        instance.resource.storage.delete(new_saved_name)
                    raise
        return instance

    def update(self, instance, validated_data):
        has_resource = "resource" in validated_data
        resource = validated_data.pop("resource", None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if has_resource:
                if resource:
                    old_resource_name = instance.resource.name if instance.resource else None
                    instance.resource.save(Path(resource.name).name, resource, save=False)
                    new_saved_name = instance.resource.name
                    try:
                        instance.save(update_fields=("resource",))
                    except Exception:
                        if new_saved_name and new_saved_name != old_resource_name:
                            instance.resource.storage.delete(new_saved_name)
                        raise
                else:
                    instance.resource = None
                    instance.save(update_fields=("resource",))
        return instance
