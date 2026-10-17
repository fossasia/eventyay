import json

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from django_scopes import scope
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField

from eventyay.base.models import SpeakerProfile, Submission, SubmissionStates, TalkQuestionTarget, User
from eventyay.base.models.cfp import default_fields
from eventyay.base.models.resource import get_slide_resources
from eventyay.base.services.etherpad import validate_etherpad_url
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.forms.fields import ImageField
from eventyay.common.forms.mixins import QuestionFieldsMixin, ReadOnlyFlag, RequestRequire
from eventyay.common.forms.renderers import InlineFormLabelRenderer, InlineFormRenderer
from eventyay.common.forms.widgets import (
    EnhancedSelect,
    EnhancedSelectMultiple,
    RichTextWidget,
    TextInputWithAddon,
)
from eventyay.common.text.phrases import phrases
from eventyay.submission.forms.resource import (
    SlidesField,
    get_slides_max_count,
    save_slides_resource,
)


class SubmissionForm(ReadOnlyFlag, RequestRequire, forms.ModelForm):
    content_locale = forms.ChoiceField(label=phrases.base.language)
    slides = SlidesField(required=False, label=_('Slides'))

    def __init__(self, event, anonymise=False, **kwargs):
        self.event = event
        instance = kwargs.get('instance')
        if anonymise:
            kwargs.pop('initial', None)
            initial = {}
            instance = kwargs.pop('instance', None)
            previous_data = instance.anonymised
            for key in self._meta.fields:
                initial[key] = previous_data.get(key) or getattr(instance, key, None) or ''
                if hasattr(initial[key], 'all'):  # Tags, for the moment
                    initial[key] = initial[key].all()
            kwargs['initial'] = initial
        kwargs['initial'] = kwargs.get('initial') or {}
        super().__init__(**kwargs)
        if 'submission_type' in self.fields:
            self.fields['submission_type'].queryset = self.event.submission_types.all()
        if not self.event.tags.all().exists():
            self.fields.pop('tags', None)
        elif 'tags' in self.fields:
            self.fields['tags'].queryset = self.event.tags.all()
            self.fields['tags'].required = False

        self.is_creating = False
        if not self.instance.pk:
            self.is_creating = True
            if not anonymise:
                self.fields['state'] = forms.ChoiceField(
                    label=_('Proposal state'),
                    choices=[
                        (choice, name)
                        for (choice, name) in SubmissionStates.get_choices()
                        if choice != SubmissionStates.DELETED and choice != SubmissionStates.DRAFT
                    ],
                    initial=SubmissionStates.SUBMITTED,
                    required=True,
                    widget=EnhancedSelect(color_field=SubmissionStates.get_color),
                )

        if 'abstract' in self.fields:
            self.fields['abstract'].widget.attrs['rows'] = 2
        if 'slides' in self.fields:
            slides_resources = list(get_slide_resources(instance)) if instance and instance.pk else []
            self.initial['slides'] = slides_resources
            self.fields['slides'].existing_resources = slides_resources
            self.fields['slides'].set_max_items(get_slides_max_count(self.event))
        if not event.get_feature_flag('present_multiple_times'):
            self.fields.pop('slot_count', None)
        if not event.tracks.exists():
            self.fields.pop('track', None)
        elif 'track' in self.fields:
            self.fields['track'].queryset = event.tracks.all()
            _cfp = getattr(self.event, 'cfp', None) if hasattr(self.event, 'cfp') else None
            track_visibility = (
                _cfp.fields.get('track', default_fields()['track']).get('visibility')
                if _cfp else 'do_not_ask'
            )
            if track_visibility == 'required':
                self.fields['track'].required = True
        if 'content_locale' in self.fields:
            _cfp = getattr(self.event, 'cfp', None) if hasattr(self.event, 'cfp') else None
            saved_visibility = (
                _cfp.fields.get('content_locale', default_fields()['content_locale']).get('visibility')
                if _cfp else 'do_not_ask'
            )
            if len(self.event.content_locales) <= 1 or saved_visibility == 'do_not_ask':
                self.fields.pop('content_locale')
            else:
                choices = list(self.event.named_content_locales)
                if self.instance and self.instance.pk and self.instance.content_locale:
                    choice_codes = {c[0] for c in choices}
                    if self.instance.content_locale not in choice_codes:
                        choices.append((self.instance.content_locale, self.instance.get_content_locale_display()))
                self.fields['content_locale'].choices = choices
        # If duration is not required, point out that the default is the session type's duration,
        # but only if there is more than one session type, because otherwise users will be
        # confused what that is.
        if (
            'duration' in self.fields
            and not self.fields['duration'].required
            and 'submission_type' in self.fields
            and len(self.fields['submission_type'].queryset) > 1
        ):
            self.fields['duration'].help_text += ' ' + str(
                _('Leave empty to use the default duration for the session type.')
            )
        # Show the field only when both the platform and the event enable Etherpad.
        gs = GlobalSettingsObject().settings
        platform_ready = bool(gs.etherpad_enabled and gs.etherpad_base_url)
        if not (platform_ready and event.get_feature_flag('etherpad_enabled')):
            self.fields.pop('etherpad_url', None)

    def clean_etherpad_url(self):
        url = self.cleaned_data.get('etherpad_url')
        if url:
            try:
                validate_etherpad_url(url)
            except DjangoValidationError as exc:
                raise forms.ValidationError(_('Please enter a valid Etherpad URL.')) from exc
        return url

    def save(self, *args, **kwargs):
        if 'content_locale' not in self.fields:
            self.instance.content_locale = (
                self.event.content_locales[0] if self.event.content_locales else self.event.locale
            )
        instance = super().save(*args, **kwargs)
        if self.is_creating:
            instance._set_state(self.cleaned_data['state'], force=True)
        else:
            if 'duration' in self.changed_data:
                instance.update_duration()
            if 'track' in self.changed_data:
                instance.update_review_scores()
            if 'slot_count' in self.changed_data and 'slot_count' in self.initial:
                instance.update_talk_slots()
        if 'slides' in self.cleaned_data:
            save_slides_resource(instance, self.cleaned_data['slides'])
        return instance

    class Meta:
        model = Submission
        fields = [
            'title',
            'submission_type',
            'track',
            'tags',
            'abstract',
            'description',
            'notes',
            'internal_notes',
            'content_locale',
            'do_not_record',
            'duration',
            'slot_count',
            'image',
            'slides',
            'is_featured',
            'etherpad_url',
        ]
        widgets = {
            'tags': EnhancedSelectMultiple(color_field='color'),
            'track': EnhancedSelect(color_field='color'),
            'submission_type': EnhancedSelect,
            'abstract': RichTextWidget,
            'description': RichTextWidget,
            'notes': RichTextWidget,
            'duration': TextInputWithAddon(addon_after=_('minutes')),
        }
        field_classes = {
            'submission_type': SafeModelChoiceField,
            'tags': SafeModelMultipleChoiceField,
            'track': SafeModelChoiceField,
            'image': ImageField,
        }
        request_require = {
            'title',
            'abstract',
            'description',
            'notes',
            'slot_count',
            'image',
            'slides',
            'do_not_record',
            'content_locale',
        }


class AnonymiseForm(SubmissionForm):
    default_renderer = InlineFormRenderer

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if not instance or not instance.pk:
            raise Exception('Cannot anonymise unsaved submission.')
        kwargs['event'] = instance.event
        kwargs['anonymise'] = True
        super().__init__(*args, **kwargs)
        self._instance = instance
        to_be_removed = ['content_locale']
        for key, field in self.fields.items():
            try:
                field.plaintext = getattr(self._instance, key)
                field.required = False
            except AttributeError:
                to_be_removed.append(key)
        for key in to_be_removed:
            self.fields.pop(key, None)

    def save(self):
        anonymised_data = {'_anonymised': True}
        for key, value in self.cleaned_data.items():
            if value != getattr(self._instance, key, ''):
                anonymised_data[key] = value
        self._instance.anonymised_data = json.dumps(anonymised_data)
        self._instance.save(update_fields=['anonymised_data'])

    class Meta:
        model = Submission
        fields = [
            'title',
            'abstract',
            'description',
            'notes',
        ]
        request_require = fields


class SubmissionStateChangeForm(forms.Form):
    pending = forms.BooleanField(
        label=_('Mark the new state as “pending”'),
        help_text=_(
            'If you mark state changes as pending, they won’t be visible to speakers right away. '
            'You can always apply pending changes for some or all proposals in one go once '
            'you’re ready to make your decisions public.'
        ),
        required=False,
        initial=False,
    )


def get_speaker_choice_label(*, name: str | None, email: str) -> str:
    return f'{name} ({email})' if name else email


class AddSpeakerForm(QuestionFieldsMixin, forms.Form):
    email = forms.EmailField(
        label=phrases.cfp.speaker_email,
        help_text=_('The email address of the speaker holding the session. They will be invited to create an account.'),
        required=False,
        widget=forms.Select,
    )
    name = forms.CharField(
        label=_('Speaker name'),
        help_text=_('The name of the speaker that should be displayed publicly.'),
        required=False,
    )
    biography = forms.CharField(
        label=_('Biography'),
        required=False,
        widget=RichTextWidget(),
    )
    locale = forms.ChoiceField(
        label=_('Invite language'),
        choices=[],
        required=False,
        help_text=_('The language in which the speaker will receive their invitation email.'),
        widget=EnhancedSelect,
    )
    send_immediately = forms.BooleanField(
        label=_('Send immediately'),
        help_text=_(
            'Send the speaker information email right away. When unchecked, the email is placed '
            'in the Outbox for you to review and send later.'
        ),
        required=False,
        initial=True,
    )

    def __init__(
        self,
        *args,
        event=None,
        form_renderer=None,
        require_name=False,
        include_biography=False,
        draft_save=False,
        submission=None,
        allow_no_email=False,
        include_speaker_questions=False,
        email_autocomplete=True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.event = event
        self.require_name = require_name
        self.draft_save = draft_save
        self.submission = submission
        self.allow_no_email = allow_no_email
        self.fields['email'].hide_optional = True
        if not email_autocomplete:
            self.fields['email'].widget = forms.EmailInput(attrs={'autocomplete': 'off'})

        self.biography_required = False
        if not include_biography:
            self.fields.pop('biography', None)
        else:
            cfp_fields = event.cfp.fields if hasattr(event, 'cfp') else default_fields()
            visibility = cfp_fields.get('biography', default_fields()['biography'])['visibility']
            if visibility == 'do_not_ask':
                self.fields.pop('biography', None)
            else:
                self.biography_required = visibility == 'required'
                self.fields['biography'].required = self.biography_required and not self.draft_save
        if 'name' in self.fields:
            # CfP full name is always required.
            self.fields['name'].required = not self.draft_save
        email_key = self.add_prefix('email')
        name_key = self.add_prefix('name')
        email_widget = self.fields['email'].widget
        if isinstance(email_widget, forms.Select) and self.is_bound and (email := self.data.get(email_key)):
            name = self.data.get(name_key)
            email_widget.choices = [(email, get_speaker_choice_label(name=name, email=email))]
        if require_name:
            self.fields['email'].required = True
            self.fields['name'].required = True
        if (
            'name' in self.fields
            and self.fields['name'].required
            and self.is_bound
            and self.data.get(email_key)
            and not self.data.get(name_key)
            and event is not None
        ):
            # Only autofill the name from users who already have a speaker
            # profile for *this* event to avoid leaking names across events.
            with scope(event=event):
                existing_profile = (
                    SpeakerProfile.objects
                    .filter(event=event, user__email__iexact=self.data[email_key])
                    .select_related('user')
                    .first()
                )
            if existing_profile and existing_profile.user.fullname:
                self.data = self.data.copy()
                self.data[name_key] = existing_profile.user.fullname
        if (
            'biography' in self.fields
            and self.fields['biography'].required
            and self.is_bound
            and (email := self.data.get(email_key))
        ):
            existing_user = User.objects.filter(email__iexact=email).first()
            existing_profile = None
            if existing_user:
                with scope(event=self.event):
                    existing_profile = existing_user.profiles.filter(event=self.event).first()
            if existing_profile and existing_profile.biography:
                self.fields['biography'].required = False
        if not event.named_locales or len(event.named_locales) < 2:
            self.fields.pop('locale')
        else:
            self.fields['locale'].choices = event.named_locales
            self.fields['locale'].initial = event.locale

        # Inject no_email checkbox right after the email field when allowed.
        if self.allow_no_email and 'email' in self.fields:
            self.fields['no_email'] = forms.BooleanField(
                label=_('This speaker does not require an email'),
                help_text=_('No account or invitation email will be created for this speaker.'),
                required=False,
                initial=False,
            )
            field_order = list(self.fields.keys())
            field_order.remove('no_email')
            field_order.insert(field_order.index('email') + 1, 'no_email')
            self.fields = {k: self.fields[k] for k in field_order}

        resolved_speaker = None
        if self.is_bound and self.data.get(email_key) and event is not None:
            email = self.data[email_key]
            with scope(event=event):
                existing_profile = (
                    SpeakerProfile.objects
                    .filter(event=event, user__email__iexact=email)
                    .select_related('user')
                    .first()
                )
            if existing_profile:
                resolved_speaker = existing_profile.user

        if include_speaker_questions and event is not None:
            self.inject_questions_into_fields(
                target=TalkQuestionTarget.SPEAKER,
                event=event,
                speaker=resolved_speaker,
            )

    def save_speaker_questions(self, speaker):
        """Save submitted speaker question responses, reconciling any existing answers."""
        from eventyay.base.models import Answer

        self.speaker = speaker
        with scope(event=self.event):
            for key, value in self.cleaned_data.items():
                if key.startswith('question_'):
                    field = self.fields[key]
                    if not getattr(field, 'answer', None) and speaker:
                        existing_answer = Answer.objects.filter(
                            person=speaker,
                            question=field.question,
                        ).first()
                        if existing_answer:
                            field.answer = existing_answer
                    self.save_questions(key, value)

    @property
    def speaker_question_fields(self):
        """Return the form fields that represent custom speaker questions."""
        return [field for field in self if field.name.startswith('question_')]

    def clean(self):
        data = super().clean()

        if self.allow_no_email and data.get('no_email'):
            data['email'] = ''
            self.cleaned_data['email'] = ''
        elif data.get('name') and not data.get('email'):
            self.add_error('email', _('Please provide an email address.'))

        if not data.get('no_email') and self.submission and (email := data.get('email')):
            if self.submission.has_speaker_email(email):
                self.add_error(
                    'email',
                    _('This speaker has already been added or invited to the proposal.'),
                )

        existing_biography = False
        email = data.get('email')
        if email:
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user:
                with scope(event=self.event):
                    existing_profile = existing_user.profiles.filter(event=self.event).first()
                existing_biography = bool(existing_profile and existing_profile.biography)

        adding_speaker = bool(data.get('no_email') or email or data.get('name'))
        biography_field = self.fields.get('biography')
        if (
            not self.draft_save
            and adding_speaker
            and getattr(self, 'biography_required', False)
            and not (biography_field and biography_field.required)
            and not existing_biography
            and not data.get('biography')
        ):
            self.add_error('biography', _('This field is required.'))
        return data
class AddSpeakerInlineForm(AddSpeakerForm):
    default_renderer = InlineFormLabelRenderer
