from functools import partial

from drf_spectacular.utils import extend_schema_field
from i18nfield.rest_framework import I18nAwareModelSerializer
from rest_framework.serializers import (
    CharField,
    ModelSerializer,
    SerializerMethodField,
    SlugRelatedField,
)

from eventyay.api.mixins import PretalxSerializer
from eventyay.api.serializers.question import AnswerSerializer
from eventyay.api.serializers.room import AvailabilitySerializer
from eventyay.api.serializers.submission import ResourceSerializer
from eventyay.api.versions import LEGACY, register_serializer
from eventyay.base.models.auth import User
from eventyay.base.models.availability import Availability
from eventyay.base.models.profile import SpeakerProfile
from eventyay.base.models.question import Answer, AnswerOption, TalkQuestion
from eventyay.base.models.resource import Resource
from eventyay.base.models.review import Review
from eventyay.base.models.room import Room
from eventyay.base.models.schedule import Schedule
from eventyay.base.models.slot import TalkSlot
from eventyay.base.models.submission import Submission, SubmissionStates
from eventyay.base.models.tag import Tag
from eventyay.talk_rules.orga import (
    can_view_speaker_emails,
    can_view_speaker_names,
    enforces_hide_speaker_emails,
    enforces_hide_speaker_names,
    is_reviewer_only_for_event,
)
from eventyay.talk_rules.submission import (
    are_featured_speakers_visible,
    are_featured_submissions_visible,
)


class LegacySubmitterSerializer(ModelSerializer):
    name = CharField(source='fullname', read_only=True)
    biography = SerializerMethodField()
    avatar = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = User
        fields = ('code', 'name', 'biography', 'avatar')

    def get_biography(self, obj):
        request = self.context.get('request')
        if self.event and request and request.user.has_perm('base.orga_list_submission', self.event):
            return getattr(obj.profiles.filter(event=self.event).first(), 'biography', '')
        if self.event and self.event.cfp.public_biography:
            return getattr(obj.profiles.filter(event=self.event).first(), 'biography', '')
        return ''

    def get_avatar(self, obj):
        request = self.context.get('request')
        if self.event and request and request.user.has_perm('base.orga_list_submission', self.event):
            return obj.avatar_url
        if self.event and self.event.cfp.request_avatar and self.event.cfp.public_avatar:
            return obj.avatar_url
        return None


class LegacySubmitterOrgaSerializer(LegacySubmitterSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        event = self.event or getattr(instance, 'event', None)
        if event and request and request.user.is_authenticated:
            hide_emails = enforces_hide_speaker_emails(request.user, event) or (
                is_reviewer_only_for_event(request.user, event) and not can_view_speaker_emails(request.user, event)
            )
            if hide_emails:
                data.pop('email', None)
        return data

    class Meta(LegacySubmitterSerializer.Meta):
        fields = LegacySubmitterSerializer.Meta.fields + ('email',)


class LegacySpeakerSerializer(ModelSerializer):
    code = CharField(source='user.code')
    name = CharField(source='user.fullname')
    avatar = SerializerMethodField()
    submissions = SerializerMethodField()
    answers = SerializerMethodField()
    is_featured = SerializerMethodField()
    featured_position = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        questions = kwargs.pop('questions', [])
        self.event = kwargs.pop('event', None)
        self.questions = (
            questions if questions in ('all', ['all']) else [question for question in questions if question.isnumeric()]
        )
        super().__init__(*args, **kwargs)
        self._featured_speakers_visible: bool | None = None
        if self.event:
            request = self.context.get('request')
            is_public_view = bool(
                not request
                or not request.user.is_authenticated
                or not request.user.has_perm('base.orga_list_speakerprofile', self.event)
            )
            if is_public_view and not self.event.cfp.public_biography:
                self.fields.pop('biography', None)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        event = self.event or getattr(instance, 'event', None)
        if event:
            is_public_view = bool(
                not request
                or not request.user.is_authenticated
                or not request.user.has_perm('base.orga_list_speakerprofile', event)
            )
            if is_public_view and not event.cfp.public_biography:
                data.pop('biography', None)
        return data

    @staticmethod
    def get_avatar(obj):
        if obj.event.cfp.request_avatar and obj.event.cfp.public_avatar:
            return obj.avatar_url

    def get_submissions(self, obj):
        submissions = self.context.get('submissions')
        if submissions is not None:
            return submissions.filter(speakers__in=[obj.user]).values_list('code', flat=True)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if request and request.user.has_perm('base.orga_list_submission', obj.event):
            return obj.user.submissions.filter(event=obj.event).values_list('code', flat=True)
        if obj.event.current_schedule and obj.event.get_feature_flag('show_schedule'):
            talks = obj.event.current_schedule.talks.all()
            return obj.user.submissions.filter(event=obj.event, slots__in=talks).values_list('code', flat=True)
        if are_featured_submissions_visible(user, obj.event):
            return obj.user.submissions.filter(
                event=obj.event,
                is_featured=True,
                state__in=SubmissionStates.accepted_states,
            ).values_list('code', flat=True)
        return []

    def answers_queryset(self, obj):
        return obj.answers.all().filter(question__is_public=True, question__active=True, question__target='speaker')

    def get_answers(self, obj):
        if not self.questions:
            return []
        queryset = self.answers_queryset(obj)
        if self.questions not in ('all', ['all']):
            queryset = queryset.filter(question__in=self.questions)
        return AnswerSerializer(queryset, many=True).data

    @extend_schema_field(bool)
    def get_is_featured(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if request and request.user.has_perm('base.orga_list_speakerprofile', obj.event):
            return bool(obj.is_featured)
        if self._featured_speakers_visible is None:
            self._featured_speakers_visible = are_featured_speakers_visible(user, obj.event)
        if not self._featured_speakers_visible:
            return False
        return bool(obj.is_featured)

    @extend_schema_field(int | None)
    def get_featured_position(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if request and request.user.has_perm('base.orga_list_speakerprofile', obj.event):
            return obj.position
        if self._featured_speakers_visible is None:
            self._featured_speakers_visible = are_featured_speakers_visible(user, obj.event)
        if not self._featured_speakers_visible:
            return None
        return obj.position if obj.is_featured else None

    class Meta:
        model = SpeakerProfile
        fields = (
            'code',
            'name',
            'biography',
            'submissions',
            'avatar',
            'answers',
            'is_featured',
            'featured_position',
        )


class LegacySpeakerOrgaSerializer(LegacySpeakerSerializer):
    email = CharField(source='user.email')
    availabilities = AvailabilitySerializer(Availability.objects.none(), many=True, read_only=True)

    def answers_queryset(self, obj):
        return obj.answers.all()

    def get_submissions(self, obj):
        return obj.user.submissions.filter(event=obj.event).values_list('code', flat=True)

    class Meta(LegacySpeakerSerializer.Meta):
        fields = LegacySpeakerSerializer.Meta.fields + ('email', 'availabilities')


class LegacySpeakerReviewerSerializer(LegacySpeakerOrgaSerializer):
    def answers_queryset(self, obj):
        return obj.reviewer_answers.all()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        event = self.event or getattr(instance, 'event', None)
        if event and request and request.user.is_authenticated:
            hide_names = enforces_hide_speaker_names(request.user, event) or (
                is_reviewer_only_for_event(request.user, event) and not can_view_speaker_names(request.user, event)
            )
            hide_emails = enforces_hide_speaker_emails(request.user, event) or (
                is_reviewer_only_for_event(request.user, event) and not can_view_speaker_emails(request.user, event)
            )
            if hide_names:
                data.pop('name', None)
                data.pop('email', None)
                data.pop('biography', None)
                data.pop('avatar', None)
            elif hide_emails:
                data.pop('email', None)
        return data

    class Meta(LegacySpeakerOrgaSerializer.Meta):
        pass


class I18nSlugRelatedField(SlugRelatedField):
    def to_representation(self, obj):
        val = getattr(obj, self.slug_field)
        if hasattr(val, 'data'):
            return val.data
        return val


class LegacySlotSerializer(I18nAwareModelSerializer):
    room = I18nSlugRelatedField(slug_field='name', read_only=True)
    end = SerializerMethodField()

    @staticmethod
    def get_end(obj):
        return obj.local_end

    class Meta:
        model = TalkSlot
        fields = ('room_id', 'room', 'start', 'end')


@register_serializer()
class LegacyBreakSerializer(LegacySlotSerializer):
    class Meta:
        model = TalkSlot
        fields = ('room', 'room_id', 'start', 'end', 'description')


class LegacySubmissionSerializer(I18nAwareModelSerializer):
    submission_type = I18nSlugRelatedField(slug_field='name', read_only=True)
    track = I18nSlugRelatedField(slug_field='name', read_only=True)
    slot = LegacySlotSerializer(TalkSlot.objects.none().filter(is_visible=True), read_only=True)
    duration = SerializerMethodField()
    speakers = SerializerMethodField()
    resources = ResourceSerializer(Resource.objects.none(), read_only=True, many=True)
    title = SerializerMethodField()
    abstract = SerializerMethodField()
    description = SerializerMethodField()
    answers = SerializerMethodField()
    is_featured = SerializerMethodField()

    speaker_serializer_class = LegacySubmitterSerializer

    def __init__(self, *args, **kwargs):
        self.can_view_speakers = kwargs.pop('can_view_speakers', False)
        self.event = kwargs.pop('event', None)
        questions = kwargs.pop('questions', [])
        self.questions = questions if questions == 'all' else [question for question in questions if question]
        super().__init__(*args, **kwargs)
        self._featured_sessions_visible: bool | None = None
        for field in ('title', 'abstract', 'description'):
            partial_name = f'get_{field}'
            setattr(self, partial_name, partial(self.get_attribute, attribute=field))
            getattr(self, partial_name).__name__ = partial_name

    @staticmethod
    def get_duration(obj):
        return obj.get_duration()

    def get_speakers(self, obj):
        has_slots = bool(obj.slots.filter(is_visible=True)) and obj.state == SubmissionStates.CONFIRMED
        request = self.context.get('request')
        is_anon = bool(request and request.query_params.get('anon'))
        user = getattr(request, 'user', None)
        event = self.event or obj.event
        hide_speaker_names_for_reviewer = bool(
            user
            and user.is_authenticated
            and event
            and user.has_perm('base.orga_list_submission', event)
            and (enforces_hide_speaker_names(user, event) or not can_view_speaker_names(user, event))
        )
        is_featured_visible = (
            not is_anon
            and not hide_speaker_names_for_reviewer
            and event
            and are_featured_submissions_visible(user, event)
            and obj.is_featured
            and obj.state in SubmissionStates.accepted_states
        )
        if has_slots or self.can_view_speakers or is_featured_visible:
            return self.speaker_serializer_class(
                obj.speakers.all(),
                many=True,
                context=self.context,
                event=self.event,
            ).data
        return []

    @extend_schema_field(bool)
    def get_is_featured(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        event = self.event or obj.event
        if event and request and request.user.has_perm('base.orga_list_submission', event):
            return bool(obj.is_featured)
        if event and self._featured_sessions_visible is None:
            self._featured_sessions_visible = are_featured_submissions_visible(user, event)
        if event and not self._featured_sessions_visible:
            return False
        return bool(obj.is_featured)

    def get_attribute(self, obj, attribute=None):
        if attribute in {'abstract', 'description'} and not obj.event.cfp.is_field_public(attribute):
            return ''
        if self.can_view_speakers:
            return getattr(obj, attribute, None)
        return obj.anonymised.get(attribute) or getattr(obj, attribute, None)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.can_view_speakers:
            return data

        resources = data.get('resources') or []
        if resources and isinstance(resources[0], dict):
            public_resource_ids = {
                resource.pk for resource in instance.resources.all() if instance.event.cfp.is_resource_public(resource)
            }
            data['resources'] = [resource for resource in resources if resource.get('id') in public_resource_ids]
        if not instance.event.cfp.public_content_locale:
            data.pop('content_locale', None)
        return data

    def answers_queryset(self, obj):
        return obj.answers.all().filter(
            question__is_public=True,
            question__active=True,
            question__target='submission',
        )

    def get_answers(self, obj):
        if not self.questions:
            return []
        queryset = self.answers_queryset(obj)
        if self.questions not in ('all', ['all']):
            queryset = queryset.filter(question__in=self.questions)
        return AnswerSerializer(queryset, many=True).data

    class Meta:
        model = Submission
        fields = [
            'code',
            'speakers',
            'title',
            'submission_type',
            'submission_type_id',
            'track',
            'track_id',
            'state',
            'abstract',
            'description',
            'duration',
            'slot_count',
            'do_not_record',
            'is_featured',
            'content_locale',
            'slot',
            'image',
            'resources',
            'answers',
        ]


@register_serializer(versions=[LEGACY], class_name='TagSerializer')
class LegacyTagSerializer(PretalxSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'tag', 'description', 'color']


class LegacySubmissionOrgaSerializer(LegacySubmissionSerializer):
    tags = SerializerMethodField()
    tag_ids = SerializerMethodField()
    created = SerializerMethodField()

    speaker_serializer_class = LegacySubmitterOrgaSerializer

    def answers_queryset(self, obj):
        return obj.answers.all()

    def get_created(self, obj):
        return obj.created.astimezone(obj.event.tz).isoformat()

    def get_tags(self, obj):
        return list(obj.tags.all().values_list('tag', flat=True))

    def get_tag_ids(self, obj):
        return list(obj.tags.all().values_list('id', flat=True))

    class Meta(LegacySubmissionSerializer.Meta):
        fields = LegacySubmissionSerializer.Meta.fields + [
            'created',
            'pending_state',
            'answers',
            'notes',
            'internal_notes',
            'tags',
            'tag_ids',
        ]


class LegacySubmissionReviewerSerializer(LegacySubmissionOrgaSerializer):
    def answers_queryset(self, obj):
        return obj.reviewer_answers.all()

    class Meta(LegacySubmissionOrgaSerializer.Meta):
        pass


@register_serializer(versions=[LEGACY], class_name='ScheduleSerializer')
class LegacyScheduleSerializer(ModelSerializer):
    slots = LegacySubmissionSerializer(Submission.objects.none().filter(state=SubmissionStates.CONFIRMED), many=True)
    breaks = SerializerMethodField()

    @staticmethod
    def get_breaks(obj):
        return LegacyBreakSerializer(obj.breaks, many=True).data

    class Meta:
        model = Schedule
        fields = ('slots', 'version', 'breaks')


@register_serializer(versions=[LEGACY], class_name='RoomSerializer')
class LegacyRoomSerializer(PretalxSerializer):
    url = SerializerMethodField()
    guid = CharField(source='uuid')

    def get_url(self, obj):
        return obj.urls.edit

    class Meta:
        model = Room
        fields = (
            'id',
            'guid',
            'name',
            'description',
            'capacity',
            'position',
            'url',
        )


@register_serializer(versions=[LEGACY], class_name='RoomOrgaSerializer')
class LegacyRoomOrgaSerializer(LegacyRoomSerializer):
    availabilities = AvailabilitySerializer(many=True)

    class Meta:
        model = Room
        fields = LegacyRoomSerializer.Meta.fields + ('speaker_info', 'availabilities')


class LegacyAnswerOptionSerializer(ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ('id', 'answer')


@register_serializer(versions=[LEGACY], class_name='QuestionSerializer')
class LegacyQuestionSerializer(ModelSerializer):
    options = LegacyAnswerOptionSerializer(many=True, required=False)

    class Meta:
        model = TalkQuestion
        fields = (
            'id',
            'variant',
            'question',
            'question_required',
            'deadline',
            'required',
            'read_only',
            'freeze_after',
            'target',
            'options',
            'help_text',
            'default_answer',
            'contains_personal_data',
            'min_length',
            'max_length',
            'is_public',
            'is_visible_to_reviewers',
        )


@register_serializer(versions=[LEGACY], class_name='AnswerSerializer')
class LegacyAnswerSerializer(ModelSerializer):
    submission = SlugRelatedField(
        queryset=Submission.objects.none(),
        slug_field='code',
        required=False,
    )
    person = SlugRelatedField(
        queryset=User.objects.all(),
        slug_field='code',
        required=False,
    )
    options = LegacyAnswerOptionSerializer(many=True, required=False)
    question = LegacyQuestionSerializer(TalkQuestion.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if not request:
            return
        self.fields['question'].queryset = request.event.questions.all()
        self.fields['submission'].queryset = request.event.submissions.all()
        self.fields['review'].queryset = request.event.reviews.all()

    class Meta:
        model = Answer
        fields = (
            'id',
            'question',
            'answer',
            'answer_file',
            'submission',
            'review',
            'person',
            'options',
        )


@register_serializer(versions=[LEGACY], class_name='ReviewSerializer')
class LegacyReviewSerializer(ModelSerializer):
    submission = SlugRelatedField(slug_field='code', read_only=True)
    user = SlugRelatedField(slug_field='name', read_only=True)
    answers = SerializerMethodField()

    def get_answers(self, obj):
        return AnswerSerializer(Answer.objects.filter(review=obj), many=True).data

    class Meta:
        model = Review
        fields = [
            'id',
            'submission',
            'text',
            'score',
            'created',
            'updated',
            'answers',
            'user',
        ]
