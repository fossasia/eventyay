import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from django import forms
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from eventyay.base.import_utils import match_header, normalize_header_value
from eventyay.base.models.question import TalkQuestionTarget, TalkQuestionVariant
from eventyay.common.session_video import exclude_session_video_from_cfp_questions
from eventyay.consts import SizeKey

CREATE_QUESTION_ENABLED_PREFIX = 'create_question_enabled_'
CREATE_QUESTION_VARIANT_PREFIX = 'create_question_variant_'
CREATE_QUESTION_LABEL_PREFIX = 'create_question_label_'
CREATE_QUESTION_HEADER_PREFIX = 'create_question_header_'

IMPORTABLE_QUESTION_VARIANTS: tuple[tuple[str, str], ...] = (
    (TalkQuestionVariant.STRING, _('Text (one-line)')),
    (TalkQuestionVariant.TEXT, _('Multi-line text')),
    (TalkQuestionVariant.NUMBER, _('Number')),
    (TalkQuestionVariant.BOOLEAN, _('Confirmation')),
    (TalkQuestionVariant.URL, _('URL')),
    (TalkQuestionVariant.VIDEO, _('Video link')),
    (TalkQuestionVariant.DATE, _('Date')),
    (TalkQuestionVariant.DATETIME, _('Date and time')),
    (TalkQuestionVariant.COUNTRY, _('Country List')),
    (TalkQuestionVariant.PHONE_NUMBER, _('Phone number')),
    (TalkQuestionVariant.CHOICES, _('Radio button (Choose one option)')),
    (TalkQuestionVariant.MULTIPLE, _('Checkbox (Choose one or several options)')),
    (TalkQuestionVariant.SELECT, _('Select (one option)')),
)
IMPORTABLE_QUESTION_VARIANT_VALUES = frozenset(value for value, _label in IMPORTABLE_QUESTION_VARIANTS)
SKIP_NEW_QUESTION_HEADERS = frozenset(
    {
        normalize_header_value('ID'),
        normalize_header_value('Proposal IDs'),
        normalize_header_value('Proposal titles'),
        normalize_header_value('Confirmed'),
        normalize_header_value('Wikimedia Username'),
        normalize_header_value('Speaker IDs'),
        normalize_header_value('Speaker names'),
        normalize_header_value('Pending proposal state'),
        normalize_header_value('Created'),
        normalize_header_value('Slot Count'),
        normalize_header_value('Session image'),
        normalize_header_value('Median score'),
        normalize_header_value('Average (mean) score'),
        normalize_header_value('Resources'),
        normalize_header_value('Start (date)'),
        normalize_header_value('Start (time)'),
        normalize_header_value('End (date)'),
        normalize_header_value('End (time)'),
        normalize_header_value('Picture'),
        normalize_header_value('Picture Source'),
        normalize_header_value('Picture License'),
        normalize_header_value('Session videos'),
        normalize_header_value('Session video'),
        normalize_header_value('Video'),
        normalize_header_value('Videos'),
        normalize_header_value('Video link'),
    }
)


def _normalize_initial(initial: object) -> dict:
    if isinstance(initial, Mapping):
        return {str(key): _preserve_initial_value(value) for key, value in initial.items()}
    if isinstance(initial, str):
        try:
            data = json.loads(initial)
        except ValueError:
            return {}
        if isinstance(data, Mapping):
            return {str(key): _preserve_initial_value(value) for key, value in data.items()}
    return {}


def _preserve_initial_value(value):
    if isinstance(value, (bool, list, dict)) or value is None:
        return value
    return str(value)


_BOOLEAN_SAMPLE_VALUES = frozenset({'yes', 'no', 'true', 'false', '1', '0', 'y', 'n', 'ja', 'oui'})
_DATE_SAMPLE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_DATETIME_SAMPLE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[tT ]')
_PHONE_SAMPLE_RE = re.compile(r"^'?\+?[\d][\d\s()./-]{6,}$")
_NUMBER_SAMPLE_RE = re.compile(r'^-?\d+(?:\.\d+)?$')


def csv_sample_values(rows: Iterable[Mapping], headers: Iterable[str], *, limit: int = 25) -> dict[str, list[str]]:
    samples = {header: [] for header in headers}
    for index, row in enumerate(rows):
        if index >= limit:
            break
        for header in samples:
            value = str(row.get(header) or '').strip()
            if value:
                samples[header].append(value)
    return samples


def infer_csv_question_variant(header: str, samples: Iterable[str] | None = None) -> str:
    header_key = normalize_header_value(header)
    if any(token in header_key for token in ('video', 'clip', 'youtube', 'vimeo')):
        return TalkQuestionVariant.VIDEO
    if any(token in header_key for token in ('phone', 'tel', 'oncall', 'on call')):
        return TalkQuestionVariant.PHONE_NUMBER
    if 'country' in header_key:
        return TalkQuestionVariant.COUNTRY
    if any(token in header_key for token in ('datetime', 'availability', 'overnight')):
        return TalkQuestionVariant.DATETIME
    if 'date' in header_key:
        return TalkQuestionVariant.DATE
    values = [str(value).strip() for value in (samples or []) if str(value).strip()]
    if not values:
        return TalkQuestionVariant.STRING
    lowered = [value.casefold() for value in values]
    if all(value in _BOOLEAN_SAMPLE_VALUES for value in lowered):
        return TalkQuestionVariant.BOOLEAN
    if all(_DATE_SAMPLE_RE.match(value) for value in values):
        return TalkQuestionVariant.DATE
    if all(_DATETIME_SAMPLE_RE.match(value) for value in values):
        return TalkQuestionVariant.DATETIME
    if all(value.startswith(('http://', 'https://')) for value in values):
        if any(token in value for value in lowered for token in ('youtu', 'vimeo')):
            return TalkQuestionVariant.VIDEO
        return TalkQuestionVariant.URL
    if all(_PHONE_SAMPLE_RE.match(value) for value in values):
        return TalkQuestionVariant.PHONE_NUMBER
    if all(_NUMBER_SAMPLE_RE.match(value) for value in values):
        return TalkQuestionVariant.NUMBER
    if any('\n' in value or len(value) > 200 for value in values):
        return TalkQuestionVariant.TEXT
    return TalkQuestionVariant.STRING


def question_header_suggestions(question) -> list[str]:
    text = question.question
    suggestions = [str(text)]
    data = getattr(text, 'data', None)
    if isinstance(data, Mapping):
        suggestions.extend(str(value) for value in data.values() if value)
    return suggestions


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _unique_slug(value: str, used: set[str]) -> str:
    base = slugify(value) or 'column'
    slug = base
    index = 2
    while slug in used:
        slug = f'{base}-{index}'
        index += 1
    used.add(slug)
    return slug


def parse_new_question_specs(settings: Mapping | None) -> list[dict[str, str]]:
    """Return validated create-and-map specs from saved import settings."""
    if not isinstance(settings, Mapping):
        return []
    raw_specs = settings.get('new_questions')
    if isinstance(raw_specs, str):
        try:
            raw_specs = json.loads(raw_specs)
        except ValueError:
            raw_specs = []
    specs = []
    if isinstance(raw_specs, list):
        for item in raw_specs:
            spec = _normalize_new_question_spec(item)
            if spec:
                specs.append(spec)
        if specs:
            return specs

    headers_by_slug: dict[str, str] = {}
    for key, value in settings.items():
        if key.startswith(CREATE_QUESTION_HEADER_PREFIX) and value:
            slug = key[len(CREATE_QUESTION_HEADER_PREFIX) :]
            headers_by_slug[slug] = str(value)

    for key, value in settings.items():
        if not key.startswith(CREATE_QUESTION_ENABLED_PREFIX) or not value:
            continue
        slug = key[len(CREATE_QUESTION_ENABLED_PREFIX) :]
        header = headers_by_slug.get(slug) or ''
        spec = _normalize_new_question_spec(
            {
                'header': header,
                'label': settings.get(f'{CREATE_QUESTION_LABEL_PREFIX}{slug}') or header,
                'variant': settings.get(f'{CREATE_QUESTION_VARIANT_PREFIX}{slug}') or TalkQuestionVariant.STRING,
                'mapping': f'csv:{header}' if header else '',
            }
        )
        if spec:
            specs.append(spec)
    return specs


def _normalize_new_question_spec(item) -> dict[str, str] | None:
    if not isinstance(item, Mapping):
        return None
    header = str(item.get('header') or '').strip()
    label = str(item.get('label') or header).strip()
    mapping = str(item.get('mapping') or '').strip()
    variant = str(item.get('variant') or TalkQuestionVariant.STRING).strip()
    if not header or not label:
        return None
    if variant not in IMPORTABLE_QUESTION_VARIANT_VALUES:
        variant = TalkQuestionVariant.STRING
    if not mapping:
        mapping = f'csv:{header}'
    if not mapping.startswith('csv:'):
        return None
    return {
        'header': header,
        'label': label[:800],
        'variant': variant,
        'mapping': mapping,
    }


class CSVImportForm(forms.Form):
    file = forms.FileField(
        label=_('Import file'),
        widget=forms.FileInput(
            attrs={
                'accept': '.csv,text/csv',
                'class': 'form-control-file',
            }
        ),
    )

    def clean_file(self):
        uploaded = self.cleaned_data['file']
        if uploaded and not uploaded.name.lower().endswith('.csv'):
            raise forms.ValidationError(_('Please upload a CSV file.'))
        max_size_bytes = settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_CSV]
        if uploaded and uploaded.size > max_size_bytes:
            max_size_mb = max_size_bytes / (1024 * 1024)
            raise forms.ValidationError(
                _('Please do not upload files larger than {size:.0f} MB.').format(size=max_size_mb)
            )
        return uploaded


@dataclass(frozen=True)
class ImportField:
    identifier: str
    label: str
    required: bool = False
    help_text: str | None = None
    suggestions: list[str] | None = None
    static_choices: Iterable[tuple[str, str]] | None = None


class ImportQuestionMappingMixin:
    question_target: str = TalkQuestionTarget.SPEAKER

    def question_field_required(self, question) -> bool:
        return False

    def _add_question_fields(self):
        self.core_field_names = list(self.fields)
        self.question_field_names: list[str] = []
        self.new_question_slugs: list[str] = []
        if not self.event:
            return
        questions = self.event.talkquestions.filter(target=self.question_target, active=True).order_by('position')
        if self.question_target == TalkQuestionTarget.SUBMISSION:
            questions = exclude_session_video_from_cfp_questions(questions)
        for question in questions:
            identifier = f'question_{question.pk}'
            field_required = self.question_field_required(question)
            field = forms.ChoiceField(
                label=str(question.question),
                required=field_required,
                choices=[('', _('Keep empty'))]
                + [(f'csv:{header}', _('CSV column: "{name}"').format(name=header)) for header in self.headers],
                help_text=str(question.help_text) if question.help_text else None,
                widget=forms.Select(attrs={'class': 'form-control'}),
            )
            existing_initial = self._usable_csv_mapping(self._initial_data.get(identifier))
            if existing_initial:
                field.initial = existing_initial
            else:
                suggestion = match_header(self.headers, question_header_suggestions(question))
                if suggestion:
                    field.initial = f'csv:{suggestion}'
            self.fields[identifier] = field
            self.question_field_names.append(identifier)
        self._add_new_question_fields()

    def _usable_csv_mapping(self, value) -> str | None:
        if not isinstance(value, str) or not value.startswith('csv:'):
            return None
        header = value[4:]
        if header in self.headers:
            return value
        return None

    def _apply_mapping_initial(self, field, identifier: str, suggestions: list[str] | None = None):
        existing_initial = self._usable_csv_mapping(self._initial_data.get(identifier))
        if existing_initial:
            field.initial = existing_initial
            return
        raw_initial = self._initial_data.get(identifier)
        if isinstance(raw_initial, str) and raw_initial.startswith('static:'):
            field.initial = raw_initial
            return
        suggestion = match_header(self.headers, suggestions or [])
        if suggestion:
            field.initial = f'csv:{suggestion}'

    def _mapped_csv_headers(self) -> set[str]:
        mapped = set()
        for name, field in self.fields.items():
            if name.startswith('create_question_'):
                continue
            header = None
            if isinstance(field.initial, str) and field.initial.startswith('csv:'):
                header = field.initial[4:]
            if header:
                mapped.add(header.casefold())
        return mapped

    def _saved_new_question_specs(self) -> dict[str, dict[str, str]]:
        specs = {}
        for spec in parse_new_question_specs(self._initial_data):
            specs[spec['header'].casefold()] = spec
        return specs

    def _add_new_question_fields(self):
        mapped_headers = self._mapped_csv_headers()
        unused_headers = [
            header
            for header in self.headers
            if header.casefold() not in mapped_headers
            and normalize_header_value(header) not in SKIP_NEW_QUESTION_HEADERS
        ]
        saved_specs = self._saved_new_question_specs()
        auto_create = not self.question_field_names
        used_slugs: set[str] = set()
        for header in unused_headers:
            slug = _unique_slug(header, used_slugs)
            saved = saved_specs.get(header.casefold())
            enabled_name = f'{CREATE_QUESTION_ENABLED_PREFIX}{slug}'
            variant_name = f'{CREATE_QUESTION_VARIANT_PREFIX}{slug}'
            label_name = f'{CREATE_QUESTION_LABEL_PREFIX}{slug}'
            header_name = f'{CREATE_QUESTION_HEADER_PREFIX}{slug}'

            enabled_initial = self._initial_data.get(enabled_name)
            if enabled_initial is None:
                enabled_initial = bool(saved) or auto_create
            inferred_variant = infer_csv_question_variant(header, getattr(self, 'sample_values', {}).get(header))
            variant_initial = self._initial_data.get(variant_name) or (saved or {}).get('variant') or inferred_variant
            label_initial = self._initial_data.get(label_name) or (saved or {}).get('label', header)

            self.fields[enabled_name] = forms.BooleanField(
                required=False,
                initial=_as_bool(enabled_initial),
                label=_('Create new custom field from "{name}"').format(name=header),
                help_text=_(
                    'Creates this custom field if it does not exist yet, then maps this CSV column to it.'
                ),
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            )
            self.fields[label_name] = forms.CharField(
                required=False,
                initial=label_initial,
                max_length=800,
                label=_('New field name'),
                widget=forms.TextInput(attrs={'class': 'form-control'}),
            )
            self.fields[variant_name] = forms.ChoiceField(
                required=False,
                initial=variant_initial,
                choices=IMPORTABLE_QUESTION_VARIANTS,
                label=_('Field type'),
                widget=forms.Select(attrs={'class': 'form-control'}),
            )
            self.fields[header_name] = forms.CharField(
                required=False,
                initial=header,
                widget=forms.HiddenInput(),
            )
            self.new_question_slugs.append(slug)

    def collect_new_questions(self, cleaned: dict) -> list[dict[str, str]]:
        specs = []
        for slug in self.new_question_slugs:
            if not cleaned.get(f'{CREATE_QUESTION_ENABLED_PREFIX}{slug}'):
                continue
            header = (cleaned.get(f'{CREATE_QUESTION_HEADER_PREFIX}{slug}') or '').strip()
            spec = _normalize_new_question_spec(
                {
                    'header': header,
                    'label': cleaned.get(f'{CREATE_QUESTION_LABEL_PREFIX}{slug}') or header,
                    'variant': cleaned.get(f'{CREATE_QUESTION_VARIANT_PREFIX}{slug}') or TalkQuestionVariant.STRING,
                    'mapping': f'csv:{header}' if header else '',
                }
            )
            if spec:
                specs.append(spec)
        return specs

    @property
    def core_fields(self):
        return [self[name] for name in getattr(self, 'core_field_names', []) if name in self.fields]

    @property
    def question_fields(self):
        return [self[name] for name in getattr(self, 'question_field_names', []) if name in self.fields]

    @property
    def new_question_rows(self) -> list[dict]:
        rows = []
        for slug in getattr(self, 'new_question_slugs', []):
            header_field = self[f'{CREATE_QUESTION_HEADER_PREFIX}{slug}']
            rows.append(
                {
                    'header': header_field.value() or header_field.initial,
                    'enabled': self[f'{CREATE_QUESTION_ENABLED_PREFIX}{slug}'],
                    'label': self[f'{CREATE_QUESTION_LABEL_PREFIX}{slug}'],
                    'variant': self[f'{CREATE_QUESTION_VARIANT_PREFIX}{slug}'],
                    'header_field': header_field,
                }
            )
        return rows


SPEAKER_IMPORT_FIELDS: list[ImportField] = [
    ImportField(
        identifier='full_name',
        label=_('Full name'),
        help_text=_('If left empty, we will try to combine the selected first and last name columns.'),
        suggestions=['name', 'full name', 'fullname', 'speaker', 'speaker name', 'speaker names'],
    ),
    ImportField(
        identifier='first_name',
        label=_('First name'),
        suggestions=['first name', 'firstname', 'given name', 'given_name'],
    ),
    ImportField(
        identifier='last_name',
        label=_('Last name'),
        suggestions=['last name', 'lastname', 'family name', 'family_name', 'surname'],
    ),
    ImportField(
        identifier='email',
        label=_('Email address'),
        required=True,
        suggestions=['email', 'email address', 'e-mail', 'e-mail address'],
    ),
    ImportField(
        identifier='biography',
        label=_('Biography'),
        suggestions=['biography', 'bio'],
    ),
    ImportField(
        identifier='job_title',
        label=_('Job title/role'),
        suggestions=['job title', 'job title/role', 'job title role', 'role'],
    ),
    ImportField(
        identifier='organization',
        label=_('Organization'),
        suggestions=['organization', 'organisation', 'company', 'company name'],
    ),
    ImportField(
        identifier='social_links',
        label=_('Social links'),
        help_text=_('Use "network: URL" pairs separated by semicolons, or a JSON list of links.'),
        suggestions=['social links', 'social media', 'social media links'],
    ),
    ImportField(
        identifier='is_featured',
        label=_('Featured'),
        help_text=_('Mark featured speakers with Yes/No or True/False values.'),
        suggestions=['featured', 'is featured'],
    ),
    ImportField(
        identifier='avatar_url',
        label=_('Profile picture URL'),
        help_text=_('A URL pointing to the speaker\'s profile picture. The image will be downloaded and saved.'),
        suggestions=['picture', 'avatar', 'profile picture', 'profile picture url', 'avatar url', 'image', 'image url', 'photo', 'photo url'],
    ),
    ImportField(
        identifier='avatar_source',
        label=_('Profile picture source'),
        help_text=_('Name the author or source of the image and include a link if available.'),
        suggestions=['avatar source', 'profile picture source', 'image source', 'picture source'],
    ),
    ImportField(
        identifier='avatar_license',
        label=_('Profile picture license'),
        help_text=_('Please provide the license name and link if applicable.'),
        suggestions=['avatar license', 'profile picture license', 'image license', 'picture license'],
    ),
    ImportField(
        identifier='identifier',
        label=_('Speaker ID'),
        help_text=_('Unique identifier for this speaker (code). Leave empty to auto-generate for new speakers.'),
        suggestions=['id', 'speaker id', 'code', 'speaker code'],
    ),
    ImportField(
        identifier='linked_submissions',
        label=_('Linked session IDs'),
        help_text=_('Comma-separated session codes or database IDs to associate with this speaker.'),
        suggestions=['session ids', 'session id', 'proposal ids', 'proposal id', 'linked sessions'],
    ),
    ImportField(
        identifier='locale',
        label=_('Invite language'),
        suggestions=['locale', 'language'],
    ),
]


class SpeakerImportProcessForm(ImportQuestionMappingMixin, forms.Form):
    question_target = TalkQuestionTarget.SPEAKER

    def __init__(self, *args, headers=None, event=None, initial=None, sample_values=None, **kwargs):
        self.headers = headers or []
        self.event = event
        self.sample_values = sample_values or {}
        initial_data = _normalize_initial(initial)
        kwargs['initial'] = initial_data
        super().__init__(*args, **kwargs)
        self._initial_data = initial_data

        header_choices = [(f'csv:{header}', _('CSV column: "{name}"').format(name=header)) for header in self.headers]
        empty_choice = [('', _('Keep empty'))]

        for field_spec in SPEAKER_IMPORT_FIELDS:
            choices = list(header_choices)
            if field_spec.static_choices:
                choices += [(f'static:{key}', label) for key, label in field_spec.static_choices]

            if field_spec.identifier == 'locale' and self.event:
                locale_choices = getattr(self.event, 'named_locales', None) or []
                if locale_choices:
                    choices = [(f'static:{code}', label) for code, label in locale_choices] + choices

            field_required = field_spec.required
            field_choices = choices if field_required else empty_choice + choices
            field = forms.ChoiceField(
                label=field_spec.label,
                required=field_required,
                choices=field_choices,
                help_text=field_spec.help_text,
                widget=forms.Select(attrs={'class': 'form-control'}),
            )

            self._apply_mapping_initial(field, field_spec.identifier, field_spec.suggestions)
            self.fields[field_spec.identifier] = field

        self._add_question_fields()

    def clean(self):
        cleaned = super().clean()
        full_name = cleaned.get('full_name')
        first_name = cleaned.get('first_name')
        last_name = cleaned.get('last_name')
        if not full_name and not (first_name and last_name):
            raise forms.ValidationError(
                _('Please provide either a full name column or both first name and last name columns.')
            )
        cleaned['new_questions'] = self.collect_new_questions(cleaned)
        return cleaned


SESSION_IMPORT_FIELDS: list[ImportField] = [
    ImportField(
        identifier='code',
        label=_('Session code'),
        help_text=_('Leave empty to auto-generate if the CSV has no unique identifier.'),
        suggestions=['id', 'code', 'session code', 'talk code', 'proposal code'],
    ),
    ImportField(
        identifier='title',
        label=_('Title'),
        required=True,
        suggestions=['proposal title', 'title', 'session title', 'talk title', 'name'],
    ),
    ImportField(
        identifier='abstract',
        label=_('Abstract'),
        suggestions=['abstract', 'summary', 'short description'],
    ),
    ImportField(
        identifier='description',
        label=_('Description'),
        suggestions=['description', 'long description', 'full description'],
    ),
    ImportField(
        identifier='linked_speakers',
        label=_('Linked speaker IDs'),
        help_text=_('Comma-separated speaker codes, emails, or names to associate with this session.'),
        suggestions=['speaker ids', 'speaker id', 'linked speakers', 'speaker email', 'speaker emails'],
    ),
    ImportField(
        identifier='submission_type',
        label=_('Session type'),
        help_text=_('Must match an existing session type name or ID.'),
        suggestions=['type', 'session type', 'proposal type'],
    ),
    ImportField(
        identifier='track',
        label=_('Track'),
        help_text=_('Must match an existing track name or ID. A new track will be created automatically if no match is found.'),
        suggestions=['track', 'category'],
    ),
    ImportField(
        identifier='state',
        label=_('State'),
        help_text=_('Use keywords such as submitted, accepted, confirmed, rejected.'),
        suggestions=['proposal state', 'state', 'status', 'decision'],
    ),
    ImportField(
        identifier='tags',
        label=_('Tags'),
        help_text=_('Comma-separated tag names.'),
        suggestions=['tags', 'labels'],
    ),
    ImportField(
        identifier='duration',
        label=_('Duration (minutes)'),
        help_text=_('Provide the duration in minutes.'),
        suggestions=['duration', 'duration (minutes)', 'length', 'time'],
    ),
    ImportField(
        identifier='content_locale',
        label=_('Content language'),
        help_text=_('Locale/language code like en, de, fr.'),
        suggestions=['language', 'locale', 'content locale'],
    ),
    ImportField(
        identifier='do_not_record',
        label=_('Do not record'),
        help_text=_('Map to Yes/No or True/False values to disable recording for the session.'),
        suggestions=[
            'do not record',
            "don't record this session.",
            "don't record this session",
            'recording',
            'record',
        ],
    ),
    ImportField(
        identifier='is_featured',
        label=_('Featured'),
        help_text=_('Mark featured sessions with Yes/No or True/False values.'),
        suggestions=[
            'featured',
            'is featured',
            'highlight',
            'show this session in public list of featured sessions.',
            'show this session in public list of featured sessions',
        ],
    ),
    ImportField(
        identifier='start',
        label=_('Start time'),
        help_text=_('Local event time, for example 2025-07-14 09:30.'),
        suggestions=['start', 'start time', 'begin'],
    ),
    ImportField(
        identifier='end',
        label=_('End time'),
        help_text=_('Local event time, for example 2025-07-14 10:15.'),
        suggestions=['end', 'end time', 'finish'],
    ),
    ImportField(
        identifier='room',
        label=_('Room'),
        help_text=_('Matches an existing room by name or ID, or creates a new room when needed.'),
        suggestions=['room', 'location'],
    ),
    ImportField(
        identifier='speakers',
        label=_('Speaker names'),
        help_text=_('Comma-separated speaker names to associate with this session.'),
        suggestions=['speaker names', 'speakers', 'speaker', 'names', 'presenter', 'presenters'],
    ),
    ImportField(
        identifier='notes',
        label=_('Notes'),
        suggestions=['notes', 'public notes'],
    ),
    ImportField(
        identifier='internal_notes',
        label=_('Internal notes'),
        suggestions=['internal notes', 'private notes'],
    ),
    ImportField(
        identifier='session_videos',
        label=_('Session videos'),
        help_text=_('YouTube or Vimeo URLs, one per line or separated by commas.'),
        suggestions=['session videos', 'session video', 'video', 'videos', 'video link', 'youtube', 'vimeo'],
    ),
]


class SessionImportProcessForm(ImportQuestionMappingMixin, forms.Form):
    question_target = TalkQuestionTarget.SUBMISSION

    def __init__(self, *args, headers=None, event=None, initial=None, sample_values=None, **kwargs):
        self.headers = headers or []
        self.event = event
        self.sample_values = sample_values or {}
        initial_data = _normalize_initial(initial)
        kwargs['initial'] = initial_data
        super().__init__(*args, **kwargs)
        self._initial_data = initial_data

        header_choices = [(f'csv:{header}', _('CSV column: "{name}"').format(name=header)) for header in self.headers]
        empty_choice = [('', _('Keep empty'))]

        for field_spec in SESSION_IMPORT_FIELDS:
            choices = list(header_choices)
            if field_spec.static_choices:
                choices += [(f'static:{key}', label) for key, label in field_spec.static_choices]

            if field_spec.identifier == 'content_locale' and self.event:
                locale_choices = getattr(self.event, 'named_content_locales', None) or []
                if locale_choices:
                    choices = [(f'static:{code}', label) for code, label in locale_choices] + choices

            field_required = field_spec.required
            field_choices = choices if field_required else empty_choice + choices
            field = forms.ChoiceField(
                label=field_spec.label,
                required=field_required,
                choices=field_choices,
                help_text=field_spec.help_text,
                widget=forms.Select(attrs={'class': 'form-control'}),
            )

            self._apply_mapping_initial(field, field_spec.identifier, field_spec.suggestions)
            self.fields[field_spec.identifier] = field

        self._add_question_fields()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('title'):
            raise forms.ValidationError(_('Please map a CSV column to the session title.'))
        cleaned['new_questions'] = self.collect_new_questions(cleaned)
        return cleaned
