from pathlib import Path

from drf_spectacular.utils import extend_schema_field
from rest_flex_fields.serializers import FlexFieldsSerializerMixin
from rest_framework import exceptions
from rest_framework.serializers import (
    CharField,
    EmailField,
    SerializerMethodField,
    URLField,
)

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.serializers.availability import (
    AvailabilitiesMixin,
    AvailabilitySerializer,
)
from eventyay.api.serializers.fields import UploadedFileField
from eventyay.api.versions import CURRENT_VERSIONS, register_serializer
from eventyay.base.models.auth import User
from eventyay.base.models.profile import SpeakerProfile
from eventyay.base.models.question import TalkQuestionTarget
from eventyay.talk_rules.orga import can_view_speaker_names


@register_serializer(versions=CURRENT_VERSIONS)
class SpeakerSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    code = CharField(source='user.code', read_only=True)
    fullname = CharField(source='user.fullname')
    avatar_url = URLField(read_only=True)
    avatar_source = SerializerMethodField()
    avatar_license = SerializerMethodField()
    answers = SerializerMethodField()
    submissions = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.event:
            return

        request = self.context.get('request')
        is_public_view = bool(request and not request.user.has_perm('base.orga_list_speakerprofile', self.event))

        if not self.event.cfp.request_avatar or (is_public_view and not self.event.cfp.public_avatar):
            self.fields.pop('avatar_url')
        if is_public_view and not self.event.cfp.public_biography:
            self.fields.pop('biography', None)
        if is_public_view and not self.event.cfp.is_field_public('avatar_source'):
            self.fields.pop('avatar_source', None)
        if is_public_view and not self.event.cfp.is_field_public('avatar_license'):
            self.fields.pop('avatar_license', None)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if (
            self.event
            and request
            and request.user.has_perm('base.orga_list_speakerprofile', self.event)
            and not request.user.has_perm('base.orga_update_submission', self.event)
            and not can_view_speaker_names(request.user, self.event)
        ):
            data.pop('fullname', None)
            data.pop('email', None)
            data.pop('biography', None)
            data.pop('avatar_url', None)
        return data

    @staticmethod
    def get_avatar_source(obj):
        if obj.user.has_avatar and obj.user.avatar_source != '':
            return obj.user.avatar_source

    @staticmethod
    def get_avatar_license(obj):
        if obj.user.has_avatar and obj.user.avatar_license != '':
            return obj.user.avatar_license

    @extend_schema_field(list[str])
    def get_submissions(self, obj):
        submissions = self.context.get('submissions')
        if not submissions:
            return []
        submissions = submissions.filter(speakers__in=[obj.user])
        if serializer := self.get_extra_flex_field('submissions', submissions):
            return serializer.data
        return submissions.values_list('code', flat=True)

    @extend_schema_field(list[int])
    def get_answers(self, obj):
        request = self.context.get('request')
        if self.event and request and not request.user.has_perm('base.orga_list_speakerprofile', self.event):
            qs = obj.answers.filter(
                question__event=self.event,
                question__target=TalkQuestionTarget.SPEAKER,
                question__is_public=True,
            )
            if serializer := self.get_extra_flex_field('answers', qs):
                return serializer.data
            return qs.values_list('pk', flat=True)

        questions = self.context.get('questions', [])
        qs = obj.answers.filter(
            question__in=questions,
            question__event=self.event,
            question__target=TalkQuestionTarget.SPEAKER,
        )
        if serializer := self.get_extra_flex_field('answers', qs):
            return serializer.data
        return qs.values_list('pk', flat=True)

    def update(self, instance, validated_data):
        availabilities_data = validated_data.pop('availabilities', None)
        profile = super().update(instance, validated_data)
        if availabilities_data is not None:
            self._handle_availabilities(profile, availabilities_data, field='person')
        return profile

    class Meta:
        model = SpeakerProfile
        fields = (
            'code',
            'fullname',
            'biography',
            'submissions',
            'avatar_url',
            'avatar_source',
            'avatar_license',
            'answers',
        )
        expandable_fields = {
            'submissions': (
                'eventyay.api.serializers.submission.SubmissionSerializer',
                {'read_only': True, 'many': True},
            ),
        }
        extra_expandable_fields = {
            'answers': (
                'eventyay.api.serializers.question.AnswerSerializer',
                {
                    'many': True,
                    'read_only': True,
                },
            ),
            'submissions': (
                'eventyay.api.serializers.submission.SubmissionSerializer',
                {
                    'many': True,
                    'read_only': True,
                },
            ),
        }


@register_serializer(versions=CURRENT_VERSIONS)
class SpeakerOrgaSerializer(AvailabilitiesMixin, SpeakerSerializer):
    email = EmailField(source='user.email')
    timezone = CharField(source='user.timezone', read_only=True)
    locale = CharField(source='user.locale', read_only=True)
    availabilities = AvailabilitySerializer(many=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.event:
            for field in ('avatar', 'availabilities'):
                if field not in self.fields:
                    continue
                if not getattr(self.event.cfp, f'request_{field}'):
                    self.fields.pop(field, None)
                elif getattr(self.event.cfp, f'require_{field}'):
                    self.fields[field].required = True

    class Meta(SpeakerSerializer.Meta):
        fields = SpeakerSerializer.Meta.fields + (
            'email',
            'timezone',
            'locale',
            'has_arrived',
            'availabilities',
        )
        expandable_fields = {
            'submissions': (
                'eventyay.api.serializers.submission.SubmissionSerializer',
                {'read_only': True, 'many': True},
            ),
        }


@register_serializer(versions=CURRENT_VERSIONS)
class SpeakerUpdateSerializer(SpeakerOrgaSerializer):
    avatar = UploadedFileField(required=False, source='speaker.user')

    def update(self, instance, validated_data):
        avatar = validated_data.pop('avatar', None)
        user_fields = validated_data.pop('user', None) or {}
        instance = super().update(instance, validated_data)
        for key, value in user_fields.items():
            setattr(instance.user, key, value)
            instance.user.save(update_fields=[key])
        if avatar:
            instance.avatar.save(Path(avatar.name).name, avatar, save=False)
            instance.save(update_fields=('avatar',))
            instance.user.process_image('avatar', generate_thumbnail=True)
        return instance

    def validate_email(self, value):
        value = value.lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=value).exists():
            raise exceptions.ValidationError('Email already exists in system.')
        return value

    class Meta(SpeakerOrgaSerializer.Meta):
        fields = SpeakerOrgaSerializer.Meta.fields + ('avatar',)
