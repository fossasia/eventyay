from django_scopes import scopes_disabled
from rest_framework.serializers import (
    CharField,
    SerializerMethodField,
    URLField,
    ModelSerializer,
)

from eventyay.base.models.profile import SpeakerProfile


class SpeakerSerializer(ModelSerializer):
    """Serializer for Speaker profiles in the API."""

    code = CharField(source="user.code", read_only=True)
    name = CharField(source="user.name", read_only=True)
    biography = CharField(read_only=True)
    submissions = SerializerMethodField()

    def get_submissions(self, obj):
        """Return list of submission codes for this speaker."""
        if not obj.user:
            return []
        with scopes_disabled():
            return list(
                obj.user.submissions.filter(event=obj.event)
                .values_list('code', flat=True)
            )

    class Meta:
        model = SpeakerProfile
        fields = ('code', 'name', 'biography', 'submissions')
