from rest_flex_fields.serializers import FlexFieldsSerializerMixin

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.base.models.access_code import SubmitterAccessCode


@register_serializer(versions=CURRENT_VERSIONS)
class SubmitterAccessCodeSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    class Meta:
        model = SubmitterAccessCode
        fields = (
            "id",
            "code",
            "track",
            "submission_type",
            "valid_until",
            "maximum_uses",
            "redeemed",
        )
        expandable_fields = {
            "track": (
                "eventyay.api.serializers.submission.TrackSerializer",
                {"read_only": True},
            ),
            "submission_type": (
                "eventyay.api.serializers.submission.SubmissionTypeSerializer",
                {"read_only": True},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = kwargs.get("context", {}).get("request")
        if request and hasattr(request, "event"):
            self.fields["track"].queryset = request.event.tracks.all()
            self.fields["submission_type"].queryset = (
                request.event.submission_types.all()
            )

    def create(self, validated_data):
        validated_data["event"] = getattr(self.context.get("request"), "event", None)
        return super().create(validated_data)
