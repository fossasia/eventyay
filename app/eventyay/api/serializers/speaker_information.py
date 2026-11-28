import logging
from functools import partial
from pathlib import Path

from django.core.files.storage import default_storage
from django.db import transaction
from django_scopes import scopes_disabled
from rest_flex_fields.serializers import FlexFieldsSerializerMixin
from rest_framework.exceptions import NotFound

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.serializers.fields import UploadedFileField
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.base.models.information import SpeakerInformation
from eventyay.base.models.track import Track
from eventyay.base.models.type import SubmissionType


logger = logging.getLogger(__name__)


def delete_stored_file(name: str) -> None:
    if not name or not name.strip():
        return
    try:
        default_storage.delete(name)
    except OSError:
        logger.exception('Deleting file %s failed.', name)


def delete_speaker_resource_if_unused(name: str) -> None:
    # Check every event, since an entry in another event may use the same file.
    with scopes_disabled():
        if not SpeakerInformation.objects.filter(resource=name).exists():
            delete_stored_file(name)


@register_serializer(versions=CURRENT_VERSIONS)
class SpeakerInformationSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    resource = UploadedFileField(required=False)

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
        instance = super().create(validated_data)
        if resource:
            instance.resource.save(Path(resource.name).name, resource, save=False)
            instance.save(update_fields=("resource",))
        return instance

    def update(self, instance, validated_data):
        resource = validated_data.pop("resource", None)
        with transaction.atomic():
            try:
                locked_instance = SpeakerInformation.objects.select_for_update().get(pk=instance.pk)
            except SpeakerInformation.DoesNotExist:
                raise NotFound from None
            locked_instance = super().update(locked_instance, validated_data)
            if resource:
                old_resource_name = locked_instance.resource.name
                locked_instance.resource.save(Path(resource.name).name, resource, save=False)
                locked_instance.save(update_fields=("resource",))

                if old_resource_name and old_resource_name != locked_instance.resource.name:
                    transaction.on_commit(partial(delete_speaker_resource_if_unused, name=old_resource_name))
        return locked_instance
