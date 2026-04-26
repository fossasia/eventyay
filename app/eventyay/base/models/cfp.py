import datetime as dt

from django.db import models
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField

from eventyay.common.text.phrases import phrases
from eventyay.common.urls import EventUrls

from .mixins import PretalxModel


def default_settings():
    return {
        'flow': {},
        'count_length_in': 'chars',
        'show_deadline': True,
        'hide_after_deadline': False,
    }


# Canonical lists of built-in CFP field keys, grouped by target.
# Every other module should import these instead of hard-coding field names.
BUILTIN_SESSION_FIELDS = (
    'title', 'abstract', 'description', 'notes', 'track',
    'duration', 'content_locale', 'image', 'do_not_record',
)
BUILTIN_SPEAKER_FIELDS = (
    'fullname', 'biography', 'avatar', 'avatar_source',
    'avatar_license', 'availabilities', 'additional_speaker',
)
BUILTIN_FIELD_KEYS = {
    'session': BUILTIN_SESSION_FIELDS,
    'speaker': BUILTIN_SPEAKER_FIELDS,
    'reviewer': (),
}


def normalize_field_order(order, config_key):
    """Return *order* with any missing built-in fields inserted at their
    canonical positions.

    The canonical position of a missing built-in is determined by finding
    the last present built-in with a lower canonical index and inserting
    immediately after it.  If no preceding built-in is present the missing
    field is inserted at the beginning of the list.

    This handles three cases correctly:
    - Config has no built-ins at all (newly created custom-only config).
    - Config has some built-ins but is missing others (e.g. a new built-in
      was added to the platform after the config was saved).
    - Config is already complete — returned unchanged.
    """
    builtin = list(BUILTIN_FIELD_KEYS.get(config_key, ()))
    if not builtin:
        return order
    builtin_set = set(builtin)
    missing = [f for f in builtin if f not in order]
    if not missing:
        return order
    result = list(order)
    for field in missing:
        canonical_idx = builtin.index(field)
        # Insert after the last built-in in result with a lower canonical index.
        insert_after = -1  # -1 → insert at position 0
        for i, item in enumerate(result):
            if item in builtin_set and builtin.index(item) < canonical_idx:
                insert_after = i
        result.insert(insert_after + 1, field)
    return result


def default_fields():
    return {
        'title': {
            'visibility': 'required',
            'min_length': None,
            'max_length': None,
            'public': True,
        },
        'abstract': {
            'visibility': 'required',
            'min_length': None,
            'max_length': None,
            'public': True,
        },
        'description': {
            'visibility': 'optional',
            'min_length': None,
            'max_length': None,
            'public': True,
        },
        'biography': {
            'visibility': 'required',
            'min_length': None,
            'max_length': None,
            'public': True,
        },
        'avatar': {'visibility': 'optional', 'public': True},
        'avatar_source': {'visibility': 'optional', 'public': False},
        'avatar_license': {'visibility': 'optional', 'public': False},
        'availabilities': {'visibility': 'do_not_ask', 'public': False},
        'notes': {'visibility': 'optional', 'public': False},
        'do_not_record': {'visibility': 'optional', 'public': False},
        'image': {'visibility': 'optional', 'public': True},
        'slides': {'visibility': 'optional', 'max_count': 1, 'public': True},
        'track': {'visibility': 'do_not_ask', 'public': False},
        'duration': {'visibility': 'do_not_ask', 'public': False},
        'slot_count': {'visibility': 'optional', 'public': False},
        'content_locale': {'visibility': 'required', 'public': False},
        'additional_speaker': {'visibility': 'optional', 'public': False},
        'fullname': {'visibility': 'required', 'public': True},
    }


def field_helper(cls):
    def is_field_requested(self, field):
        return self.fields.get(field, default_fields()[field])['visibility'] != 'do_not_ask'

    def is_field_required(self, field):
        return self.fields.get(field, default_fields()[field])['visibility'] == 'required'

    def is_field_public(self, field):
        return self.fields.get(field, default_fields()[field]).get(
            'public', default_fields()[field].get('public', False)
        )

    for field in default_fields().keys():
        # Create wrapper functions with clean docstrings to avoid RST formatting issues
        def make_request_getter(field_name):
            def getter(self):
                return is_field_requested(self, field_name)

            getter.__doc__ = f'Check if {field_name} field is requested.'
            return getter

        def make_require_getter(field_name):
            def getter(self):
                return is_field_required(self, field_name)

            getter.__doc__ = f'Check if {field_name} field is required.'
            return getter

        def make_public_getter(field_name):
            def getter(self):
                return is_field_public(self, field_name)

            getter.__doc__ = f'Check if {field_name} field is public.'
            return getter

        setattr(cls, f'request_{field}', property(make_request_getter(field)))
        setattr(cls, f'require_{field}', property(make_require_getter(field)))
        setattr(cls, f'public_{field}', property(make_public_getter(field)))
    return cls


@field_helper
class CfP(PretalxModel):
    """Every :class:`~pretalx.event.models.event.Event` has one Call for
    Papers/Participation/Proposals.

    :param deadline: The regular deadline. Please note that submissions can be available for longer than this
                     if different deadlines are configured on single submission types.
    """

    event = models.OneToOneField(to='Event', on_delete=models.PROTECT)
    headline = I18nCharField(max_length=300, null=True, blank=True, verbose_name=_('headline'))
    text = I18nTextField(
        null=True,
        blank=True,
        verbose_name=_('text'),
        help_text=phrases.base.use_markdown,
    )
    default_type = models.ForeignKey(
        to='SubmissionType',
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name=_('Default session type'),
        null=True,
        blank=True,
        help_text=_(
            'The default session type for new submissions. Leave empty to show no pre-selected type in the CFP form.'
        ),
    )
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Deadline'),
        help_text=_('Please put in the last date you want to accept proposals from users.'),
    )
    settings = models.JSONField(default=default_settings)
    fields = models.JSONField(default=default_fields)

    class urls(EventUrls):
        """URL patterns for public CfP (Call for Proposals) views."""

        base = '{self.event.orga_urls.cfp}'
        editor = '{base}flow/'
        questions = '{base}questions/'
        new_question = '{questions}new/'
        remind_questions = '{questions}remind/'
        text = edit_text = '{base}text'
        types = '{base}types/'
        new_type = '{types}new'
        tracks = '{base}tracks/'
        new_track = '{tracks}new/'
        access_codes = '{base}access-codes/'
        new_access_code = '{access_codes}new/'
        public = '{self.event.urls.base}cfp'
        submit = '{self.event.urls.base}submit/'

    def __str__(self) -> str:
        """Help with debugging."""
        return f'CfP(event={self.event.slug})'

    def is_resource_public(self, resource) -> bool:
        return resource.kind != 'slides' or self.public_slides

    def copy_data_from(self, other_cfp, skip_attributes=None):
        # default_type gets set by event.copy_data_from
        clonable_attributes = [
            'headline',
            'text',
            'deadline',
            'settings',
            'fields',
        ]
        if skip_attributes:
            clonable_attributes = [attr for attr in clonable_attributes if attr not in skip_attributes]
        for field in clonable_attributes:
            setattr(self, field, getattr(other_cfp, field))
        self.save()

    @cached_property
    def is_open(self) -> bool:
        """``True`` if ``max_deadline`` is not over yet, or if no deadline is
        set."""
        if self.deadline is None:
            return True
        return self.max_deadline >= now() if self.max_deadline else True

    @cached_property
    def max_deadline(self) -> dt.datetime:
        """Returns the latest date any submission is possible.

        This includes the deadlines set on any submission type for this
        event.
        """
        deadlines = list(self.event.submission_types.filter(deadline__isnull=False).values_list('deadline', flat=True))
        if self.deadline:
            deadlines.append(self.deadline)
        return max(deadlines) if deadlines else None
