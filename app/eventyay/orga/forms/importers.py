import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Iterable, List, Optional

from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.models.question import TalkQuestionRequired, TalkQuestionTarget


def _normalize_initial(initial) -> dict:
    if isinstance(initial, Mapping):
        return dict(initial)
    if isinstance(initial, str):
        try:
            data = json.loads(initial)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _normalize_header_value(value: Optional[str]) -> str:
    if not value:
        return ''
    return ''.join(value.lower().replace('-', ' ').replace('_', ' ').split())


def _match_header(headers: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    header_map = {_normalize_header_value(header): header for header in headers}
    for candidate in candidates:
        normalized = _normalize_header_value(candidate)
        if normalized in header_map:
            return header_map[normalized]
    return None


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
        if uploaded and uploaded.size > 10 * 1024 * 1024:
            raise forms.ValidationError(_('Please do not upload files larger than 10 MB.'))
        return uploaded


@dataclass(frozen=True)
class ImportField:
    identifier: str
    label: str
    required: bool = False
    help_text: Optional[str] = None
    suggestions: Optional[List[str]] = None
    static_choices: Optional[Iterable[tuple[str, str]]] = None


SPEAKER_IMPORT_FIELDS: List[ImportField] = [
    ImportField(
        identifier='full_name',
        label=_('Full name'),
        help_text=_('If left empty, we will try to combine the selected first and last name columns.'),
        suggestions=['name', 'full name', 'fullname'],
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
        identifier='avatar_url',
        label=_('Profile picture URL'),
        help_text=_('Provide a publicly reachable URL. The importer will try to download and attach the image.'),
        suggestions=['avatar', 'avatar url', 'profile picture', 'profile picture url', 'picture'],
    ),
    ImportField(
        identifier='avatar_source',
        label=_('Profile picture source'),
        help_text=_('Name the author or source of the image and include a link if available.'),
        suggestions=['avatar source', 'profile picture source', 'image source'],
    ),
    ImportField(
        identifier='avatar_license',
        label=_('Profile picture license'),
        help_text=_('Please provide the license name and link if applicable.'),
        suggestions=['avatar license', 'profile picture license', 'image license'],
    ),
    ImportField(
        identifier='identifier',
        label=_('Speaker ID'),
        help_text=_('Unique identifier for this speaker (code). Leave empty to auto-generate.'),
        suggestions=['id', 'speaker id', 'code', 'speaker code'],
    ),
    ImportField(
        identifier='linked_submissions',
        label=_('Linked proposal IDs'),
        help_text=_('Comma-separated session codes or IDs to associate with this speaker.'),
        suggestions=['proposal ids', 'proposal id', 'session ids', 'linked proposals'],
    ),
    ImportField(
        identifier='locale',
        label=_('Invite language'),
    ),
]


class SpeakerImportProcessForm(forms.Form):
    def __init__(self, *args, headers=None, event=None, initial=None, **kwargs):
        self.headers = headers or []
        self.event = event
        initial_data = _normalize_initial(initial)
        kwargs['initial'] = initial_data
        super().__init__(*args, **kwargs)
        self._initial_data = initial_data

        header_choices = [('csv:{}'.format(h), _('CSV column: "{name}"').format(name=h)) for h in self.headers]
        empty_choice = [('', _('Keep empty'))]

        for field_spec in SPEAKER_IMPORT_FIELDS:
            choices = header_choices.copy()
            if field_spec.static_choices:
                choices += [('static:{}'.format(key), label) for key, label in field_spec.static_choices]

            if field_spec.identifier == 'locale' and self.event:
                locale_choices = getattr(self.event, 'named_locales', None)
                if locale_choices:
                    choices = [('static:{}'.format(code), label) for code, label in locale_choices] + choices

            field_required = field_spec.required
            field_choices = choices if field_required else empty_choice + choices
            field = forms.ChoiceField(
                label=field_spec.label,
                required=field_required,
                choices=field_choices,
                help_text=field_spec.help_text,
                widget=forms.Select(attrs={'class': 'form-control'}),
            )

            # Try to find a matching column automatically
            existing_initial = self._initial_data.get(field_spec.identifier)
            if existing_initial:
                field.initial = existing_initial
            else:
                suggested = self._find_suggestion(field_spec)
                if suggested:
                    field.initial = suggested

            self.fields[field_spec.identifier] = field

    def _find_suggestion(self, field_spec: ImportField) -> Optional[str]:
        match = _match_header(self.headers, field_spec.suggestions or [])
        if match:
            return f'csv:{match}'
        return None

    def clean(self):
        cleaned = super().clean()
        full_name = cleaned.get('full_name')
        first_name = cleaned.get('first_name')
        last_name = cleaned.get('last_name')
        if not full_name and not (first_name and last_name):
            raise forms.ValidationError(
                _('Please provide either a full name column or both first name and last name columns.')
            )
        return cleaned


SESSION_IMPORT_FIELDS: List[ImportField] = [
    ImportField(
        identifier='code',
        label=_('Session code'),
        help_text=_('Leave empty to auto-generate if the CSV has no unique identifier.'),
        suggestions=['code', 'session code', 'talk code', 'proposal code'],
    ),
    ImportField(
        identifier='title',
        label=_('Title'),
        required=True,
        suggestions=['title', 'session title', 'talk title', 'name'],
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
        help_text=_('Comma-separated speaker codes or emails to associate with this session.'),
        suggestions=['speaker ids', 'speaker id', 'speakers', 'speaker emails'],
    ),
    ImportField(
        identifier='submission_type',
        label=_('Session type'),
        help_text=_('Must match an existing session type name.'),
        suggestions=['type', 'session type', 'proposal type'],
    ),
    ImportField(
        identifier='track',
        label=_('Track'),
        help_text=_('Must match an existing track name.'),
        suggestions=['track', 'category'],
    ),
    ImportField(
        identifier='state',
        label=_('State'),
        help_text=_('Use submission state keywords such as submitted, accepted, confirmed, rejected.'),
        suggestions=['state', 'status', 'decision'],
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
        suggestions=['duration', 'length', 'time'],
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
        help_text=_('Map to Yes/No values to disable recording for the session.'),
        suggestions=['do not record', 'recording', 'record'],
    ),
    ImportField(
        identifier='is_featured',
        label=_('Featured'),
        help_text=_('Mark featured sessions with Yes/No values.'),
        suggestions=['featured', 'is featured', 'highlight'],
    ),
    ImportField(
        identifier='start',
        label=_('Start time'),
        help_text=_('Local event time, e.g. 2025-07-14 09:30.'),
        suggestions=['start', 'start time', 'begin'],
    ),
    ImportField(
        identifier='end',
        label=_('End time'),
        help_text=_('Local event time, e.g. 2025-07-14 10:15.'),
        suggestions=['end', 'end time', 'finish'],
    ),
    ImportField(
        identifier='room',
        label=_('Room'),
        help_text=_('Must match an existing room name.'),
        suggestions=['room', 'location'],
    ),
    ImportField(
        identifier='speakers',
        label=_('Speaker names'),
        help_text=_('Comma-separated speaker display names to associate with this session.'),
        suggestions=['speaker names', 'speakers', 'names'],
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
]


class SessionImportProcessForm(forms.Form):
    def __init__(self, *args, headers=None, event=None, initial=None, **kwargs):
        self.headers = headers or []
        self.event = event
        initial_data = _normalize_initial(initial)
        kwargs['initial'] = initial_data
        super().__init__(*args, **kwargs)
        self._initial_data = initial_data

        header_choices = [('csv:{}'.format(h), _('CSV column: "{name}"').format(name=h)) for h in self.headers]
        empty_choice = [('', _('Keep empty'))]

        for field_spec in SESSION_IMPORT_FIELDS:
            choices = header_choices.copy()
            if field_spec.static_choices:
                choices += [('static:{}'.format(key), label) for key, label in field_spec.static_choices]

            field_required = field_spec.required
            field_choices = choices if field_required else empty_choice + choices
            field = forms.ChoiceField(
                label=field_spec.label,
                required=field_required,
                choices=field_choices,
                help_text=field_spec.help_text,
                widget=forms.Select(attrs={'class': 'form-control'}),
            )

            existing_initial = self._initial_data.get(field_spec.identifier)
            if existing_initial:
                field.initial = existing_initial
            else:
                suggested = self._find_suggestion(field_spec)
                if suggested:
                    field.initial = suggested

            self.fields[field_spec.identifier] = field

        self._add_question_fields()

    def _find_suggestion(self, field_spec: ImportField) -> Optional[str]:
        match = _match_header(self.headers, field_spec.suggestions or [])
        if match:
            return f'csv:{match}'
        return None

    def _add_question_fields(self):
        if not self.event:
            return
        questions = (
            self.event.talkquestions.filter(target=TalkQuestionTarget.SUBMISSION, active=True)
            if hasattr(self.event, 'talkquestions')
            else []
        )
        initial_data = getattr(self, '_initial_data', {})
        for question in questions:
            identifier = f'question_{question.pk}'
            field_required = question.question_required == TalkQuestionRequired.REQUIRED
            field = forms.ChoiceField(
                label=str(question.question),
                required=field_required,
                choices=[('', _('Keep empty'))] + [
                    ('csv:{}'.format(h), _('CSV column: "{name}"').format(name=h)) for h in self.headers
                ],
                help_text=str(question.help_text) if question.help_text else None,
                widget=forms.Select(attrs={'class': 'form-control'}),
            )
            existing_initial = initial_data.get(identifier)
            if existing_initial:
                field.initial = existing_initial
            else:
                suggestion = _match_header(self.headers, [str(question.question)])
                if suggestion:
                    field.initial = f'csv:{suggestion}'
            self.fields[identifier] = field

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('title'):
            raise forms.ValidationError(_('Please map a CSV column to the session title.'))
        return cleaned
