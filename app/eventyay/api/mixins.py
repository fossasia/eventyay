from django.db.models import Prefetch
from django.utils.cache import patch_cache_control
from django.utils.functional import cached_property
from django.utils.http import http_date
from drf_spectacular.utils import extend_schema_field
from i18nfield.fields import I18nCharField, I18nTextField
from i18nfield.rest_framework import I18nField
from rest_flex_fields import is_expanded
from rest_flex_fields.utils import split_levels
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer
from rest_framework.settings import api_settings

from eventyay.api.versions import get_api_version_from_request, get_serializer_by_version
from eventyay.base.models import Answer, SpeakerProfile, User
from eventyay.base.models.question import TalkQuestionTarget
from eventyay.base.services.stale_cache import (
    CATALOG_HOT_TTL,
    api_cache_fingerprint,
    api_locale_key,
    get_cached_catalog_list,
)


class ApiVersionException(exceptions.APIException):
    status_code = 400
    default_detail = "API version not supported."
    default_code = "invalid_version"


class PretalxViewSetMixin:
    endpoint = None
    logtype_map = {
        "create": ".create",
        "update": ".update",
        "partial_update": ".update",
    }

    @cached_property
    def api_version(self):
        try:
            return get_api_version_from_request(self.request)
        except Exception:
            raise ApiVersionException()

    def get_versioned_serializer(self, name):
        try:
            return get_serializer_by_version(name, self.api_version)
        except KeyError:
            raise ApiVersionException()

    def get_serializer_class(self):
        if hasattr(self, "get_unversioned_serializer_class"):
            base_class = self.get_unversioned_serializer_class()
        elif hasattr(self, "serializer_class"):
            base_class = self.serializer_class
        return self.get_versioned_serializer(base_class.__name__)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        locale = self.request.GET.get("lang")
        if locale and locale in self.event.locales:
            context["override_locale"] = locale
        return context

    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance.log_action(".create", person=self.request.user, auth=self.request.auth, orga=True)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        serializer.instance.log_action(".update", person=self.request.user, auth=self.request.auth, orga=True)

    @cached_property
    def event(self):
        # request.event is not present when building API docs
        return getattr(self.request, "event", None)

    def has_perm(self, permission, obj=None):
        model = getattr(self, "model", None) or self.queryset.model
        permission_name = model.get_perm(permission)
        return self.request.user.has_perm(permission_name, obj or self.event)

    def check_expanded_fields(self, *args):
        return [arg for arg in args if is_expanded(self.request, arg)]


@extend_schema_field(
    field={
        "type": "object",
        "additionalProperties": {"type": "string"},
        "example": {"en": "English text", "de": "Deutscher Text"},
    },
    component_name="Multi-language string",
)
class DocumentedI18nField(I18nField):
    def to_representation(self, value):
        context = getattr(self.parent, "context", None) or {}
        if context.get("override_locale"):
            return str(value)
        return super().to_representation(value)


class PretalxSerializer(ModelSerializer):
    """
    This serializer class will behave like the i18nfield serializer,
    outputting a dict/object for internationalized strings, unless if
    when it was initialized with an ``override_locale`` (taken from
    a URL queryparam, usually), in which case the string will be cast
    to the locale in question – relying on either a view or a middleware
    to apply the locale manager.
    """

    def __init__(self, *args, **kwargs):
        self.override_locale = kwargs.get("context", {}).get("override_locale")
        self.event = getattr(kwargs.get("context", {}).get("request"), "event", None)
        super().__init__(*args, **kwargs)

    def get_with_fallback(self, data, key):
        """
        Get key from dictionary, or fall back to `self.instance` if it exists.
        Handy for validating data in partial updates.
        (Yes, not terribly safe, but better than nothing.)
        """
        if key in data:
            return data[key]
        if self.instance:
            return getattr(self.instance, key, None)

    @cached_property
    def extra_flex_field_config(self):
        return {
            key: split_levels(self._flex_options_all[key])
            for key in ("expand", "fields", "omit")
        }

    def get_extra_flex_field(self, extra_field, *args, **kwargs):
        if extra_field in self.extra_flex_field_config["expand"][0]:
            klass, settings = self.Meta.extra_expandable_fields[extra_field]
            serializer_class = self._get_serializer_class_from_lazy_string(klass)
            settings["context"] = self.context
            settings["parent"] = self
            for key, value in self.extra_flex_field_config.items():
                if value[1] and extra_field in value[1]:
                    settings[key] = value[1][extra_field]
            return serializer_class(*args, **settings, **kwargs)


PretalxSerializer.serializer_field_mapping[I18nCharField] = DocumentedI18nField
PretalxSerializer.serializer_field_mapping[I18nTextField] = DocumentedI18nField


def request_is_private(request):
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return True
    return getattr(request, 'auth', None) is not None


def cached_json_response(request, data, *, max_age, updated_at=None, etag=None):
    etag = etag or api_cache_fingerprint(data)
    etag_header = f'"{etag}"'
    if_none_match = request.headers.get('If-None-Match', '')
    if etag_header in {part.strip() for part in if_none_match.split(',')}:
        response = Response(status=304)
    else:
        response = Response(data)

    if request_is_private(request):
        patch_cache_control(response, no_store=True)
    else:
        patch_cache_control(
            response,
            max_age=max_age,
            public=True,
            stale_while_revalidate=max_age,
        )
    response['ETag'] = etag_header
    if updated_at is not None:
        response['Last-Modified'] = http_date(updated_at.timestamp())
    return response


class CachedCatalogListMixin:
    catalog_name = None
    catalog_max_age = CATALOG_HOT_TTL
    pagination_class = None

    def uses_catalog_list_cache(self):
        if not self.event or not self.catalog_name:
            return False
        pagination_class = getattr(self, 'pagination_class', api_settings.DEFAULT_PAGINATION_CLASS)
        if pagination_class is not None:
            return False
        request = getattr(self, 'request', None)
        if request is not None:
            params = getattr(request, 'query_params', getattr(request, 'GET', {}))
            # Search/ordering still apply in filter_queryset(); do not reuse the
            # unfiltered catalog entry for those responses.
            if params.get('search') or params.get('ordering'):
                return False
        return True

    def list(self, request, *args, **kwargs):
        if not self.uses_catalog_list_cache():
            return super().list(request, *args, **kwargs)

        def loader():
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        locale_key = api_locale_key(request, self.event)
        data, etag = get_cached_catalog_list(self.event.pk, self.catalog_name, locale_key, loader)
        return cached_json_response(request, data, max_age=self.catalog_max_age, etag=etag)


def prefetch_submission_speakers(queryset, event):
    return queryset.prefetch_related(
        Prefetch(
            'speakers',
            queryset=User.objects.prefetch_related(
                Prefetch(
                    'profiles',
                    queryset=SpeakerProfile.objects.filter(event=event),
                ),
            ),
        ),
    )


def prefetch_submission_relations(queryset, event, expanded_fields=()):
    queryset = queryset.select_related('event', 'track', 'submission_type')
    queryset = queryset.prefetch_related('speakers', 'slots')
    expand = set(expanded_fields)
    if 'speakers.user' in expand:
        queryset = prefetch_submission_speakers(queryset, event)
    answer_fields = [field for field in expanded_fields if field.startswith('answers')]
    if answer_fields:
        prefetch_fields = [field.replace('.', '__') for field in answer_fields]
        if any(name.startswith('answers') for name in prefetch_fields):
            prefetch_fields = ['answers'] + prefetch_fields
        queryset = queryset.prefetch_related(*prefetch_fields)
    slot_fields = [field for field in expanded_fields if field.startswith('slots')]
    if slot_fields:
        queryset = queryset.prefetch_related(*[field.replace('.', '__') for field in slot_fields])
    if 'resources' in expand:
        queryset = queryset.prefetch_related('resources')
    return queryset


def prefetch_talk_slots(queryset, event, expanded_fields=()):
    expand = set(expanded_fields)
    if 'submission.speakers' in expand or 'slots.submission.speakers' in expand:
        queryset = queryset.prefetch_related(
            Prefetch(
                'submission__speakers',
                queryset=User.objects.prefetch_related(
                    Prefetch(
                        'profiles',
                        queryset=SpeakerProfile.objects.filter(event=event),
                    ),
                ),
            ),
        )
    submission_prefetches = []
    for field in (
        'submission.resources',
        'submission.answers',
        'submission.answers.question',
        'submission.answers.question.tracks',
        'submission.answers.question.submission_types',
        'submission.tags',
    ):
        if field in expand:
            submission_prefetches.append(field.replace('.', '__'))
    if submission_prefetches:
        if any(name.startswith('submission__answers') for name in submission_prefetches):
            submission_prefetches = ['submission__answers'] + submission_prefetches
        queryset = queryset.prefetch_related(*submission_prefetches)
    return queryset


def prefetch_speaker_profiles(queryset, event):
    return queryset.select_related('user', 'event', 'event__cfp').prefetch_related(
        'social_links',
        Prefetch(
            'user',
            queryset=User.objects.prefetch_related(
                Prefetch(
                    'answers',
                    queryset=Answer.objects.filter(question__event=event).select_related('question'),
                    to_attr='event_answers',
                ),
            ),
        ),
    )


def filter_public_speaker_answers(user, *, is_public_only):
    answers = getattr(user, 'event_answers', None)
    if answers is None:
        return None
    if not is_public_only:
        return answers
    return [
        answer
        for answer in answers
        if answer.question.target == TalkQuestionTarget.SPEAKER and answer.question.is_public
    ]

