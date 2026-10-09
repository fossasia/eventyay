import json
import logging

from django import forms
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField
from i18nfield.forms import I18nFormField, I18nFormMixin, I18nModelForm, I18nTextarea, I18nTextInput
from i18nfield.strings import LazyI18nString
from eventyay.common.forms.fields import I18nRichTextFormField
from eventyay.common.sanitizers import sanitize_rich_text
from eventyay.base.models import (
    AnswerOption,
    SubmissionType,
    SubmitterAccessCode,
    TalkQuestion,
    TalkQuestionTarget,
    TalkQuestionVariant,
    Track,
)
from eventyay.base.models.cfp import CfP, default_fields
from eventyay.base.models.question import TalkQuestionRequired
from eventyay.common.session_video import (
    ensure_session_video_question,
    exclude_session_video_from_cfp_questions,
    get_session_video_question,
)
from eventyay.common.forms.fields import ColorField
from eventyay.common.forms.mixins import I18nHelpText, JsonSubfieldMixin, ReadOnlyFlag
from eventyay.common.forms.renderers import InlineFormRenderer
from eventyay.common.forms.widgets import (
    EnhancedSelect,
    EnhancedSelectMultiple,
    HtmlDateInput,
    HtmlDateTimeInput,
    TextInputWithAddon,
)
from eventyay.common.language import get_language_choices_native_with_ui_name, language
from eventyay.common.text.phrases import phrases
from eventyay.control.forms import MultipleLanguagesWidget
from eventyay.orga.utils.colors import generate_random_high_contrast_color

logger = logging.getLogger(__name__)


class CfPGeneralSettingsForm(ReadOnlyFlag, I18nHelpText, JsonSubfieldMixin, I18nFormMixin, forms.Form):
    """
    Form for general CfP settings stored in event.cfp.settings.
    requires an 'obj' argument in __init__ which must be an Event instance with a related 'cfp' object.
    """

    use_tracks = forms.BooleanField(
        label=_('Use tracks'),
        required=False,
        help_text=_('Do you organise your sessions by tracks?'),
    )
    present_multiple_times = forms.BooleanField(
        label=_('Slot Count'),
        required=False,
        help_text=_('Can sessions be held multiple times?'),
    )
    mail_on_new_submission = forms.BooleanField(
        label=_('Send mail on new proposal'),
        help_text=_(
            'If this setting is checked, all event admins will receive an email notification '
            'for every received proposal.'
        ),
        required=False,
    )
    submission_public_review = forms.BooleanField(
        label=_('Allow submitters to share their proposal publicly'),
        help_text=_('Allow submitters to share a secret link to their proposal with others.'),
        required=False,
    )
    count_length_in = forms.ChoiceField(
        label=_('Count text length in'),
        choices=(('chars', _('Characters')), ('words', _('Words'))),
        widget=forms.RadioSelect(),
        required=False,
    )
    cfp_enable_gravatar = forms.BooleanField(
        label=_('Enable Gravatar'),
        help_text=_('Allow speakers to use Gravatar for their profile picture.'),
        required=False,
    )

    def __init__(self, *args, obj, **kwargs):
        kwargs.pop('read_only')  # added in ActionFromUrl view mixin, but not needed here.
        self.instance = obj
        super().__init__(*args, **kwargs)
        self.initial['count_length_in'] = obj.cfp.settings.get('count_length_in', 'chars')
        self.initial['cfp_enable_gravatar'] = obj.cfp.enable_gravatar

    def save(self, *args, **kwargs):
        persist_cfp = kwargs.pop('persist_cfp', True)
        update_count_length_in = kwargs.pop('update_count_length_in', True)

        if update_count_length_in:
            current_count_length_in = self.instance.cfp.settings.get('count_length_in', 'chars')
            if 'count_length_in' in self.cleaned_data:
                new_count_length_in = self.cleaned_data.get('count_length_in') or current_count_length_in
            else:
                new_count_length_in = current_count_length_in
            self.instance.cfp.settings['count_length_in'] = new_count_length_in

        if persist_cfp:
            self.instance.cfp.save(update_fields=['settings'])
        super().save(*args, **kwargs)

    class Meta:
        # These are JSON fields on event.settings
        json_fields = {
            'use_tracks': 'feature_flags',
            'submission_public_review': 'feature_flags',
            'present_multiple_times': 'feature_flags',
            'mail_on_new_submission': 'mail_settings',
        }


class CfPSettingsForm(CfPGeneralSettingsForm):
    """
    Form for full CfP settings, including specific field requirements and custom questions.
    """

    class Meta(CfPGeneralSettingsForm.Meta):
        # The boolean feature-flag fields (use_tracks, present_multiple_times, etc.) are
        # inherited from CfPGeneralSettingsForm but are NOT rendered on the Forms page
        # template.  If JsonSubfieldMixin.save() were to process them here it would read
        # False from the missing POST keys and silently overwrite the stored values.
        # Override to empty so those flags are only written from CfPGeneralSettingsForm
        # (the Content page), where the checkboxes are actually rendered.
        json_fields = {}

    def __init__(self, *args, obj, **kwargs):
        super().__init__(*args, obj=obj, **kwargs)
        self.fields.pop('cfp_enable_gravatar', None)
        self.length_fields = [
            'title',
            'abstract',
            'description',
            'biography',
            'job_title',
            'organization',
            'avatar_source',
            'avatar_license',
        ]
        self.request_require_fields = [
            'abstract',
            'description',
            'notes',
            'biography',
            'job_title',
            'organization',
            'avatar',
            'avatar_source',
            'avatar_license',
            'additional_speaker',
            'availabilities',
            'do_not_record',
            'image',
            'slides',
            'session_videos',
            'track',
            'duration',
            'slot_count',
            'content_locale',
            'fullname',
            'social_links',
        ]
        self.public_fields = [
            'title',
            'abstract',
            'description',
            'track',
            'duration',
            'content_locale',
            'image',
            'slides',
            'fullname',
            'biography',
            'job_title',
            'organization',
            'avatar',
            'social_links',
        ]
        for attribute in self.length_fields:
            field_name = f'cfp_{attribute}_min_length'
            self.fields[field_name] = forms.IntegerField(
                required=False,
                min_value=0,
                initial=obj.cfp.fields.get(attribute, {'min_length': None}).get('min_length'),
            )
            self.fields[field_name].widget.attrs['placeholder'] = ''
            field_name = f'cfp_{attribute}_max_length'
            self.fields[field_name] = forms.IntegerField(
                required=False,
                min_value=0,
                initial=obj.cfp.fields.get(attribute, {'max_length': None}).get('max_length'),
            )
            self.fields[field_name].widget.attrs['placeholder'] = ''
        self.fields['cfp_slides_max_count'] = forms.IntegerField(
            required=False,
            min_value=1,
            initial=obj.cfp.fields.get('slides', default_fields()['slides']).get('max_count', 1),
            help_text=_('Maximum number of slide links or PDF files per proposal.'),
        )
        self.fields['cfp_slides_max_count'].widget.attrs['placeholder'] = ''
        for attribute in self.request_require_fields:
            field_name = f'cfp_ask_{attribute}'
            # Full Name is always required and always active
            if attribute == 'fullname':
                self.fields[field_name] = forms.ChoiceField(
                    required=True,
                    initial='required',
                    choices=[
                        ('required', _('Ask and require input')),
                    ],
                    widget=forms.Select(attrs={'disabled': True, 'aria-readonly': 'true'}),
                )
            else:
                self.fields[field_name] = forms.ChoiceField(
                    required=True,
                    initial=obj.cfp.fields.get(attribute, default_fields()[attribute])['visibility'],
                    choices=[
                        ('do_not_ask', _('Do not ask')),
                        ('optional', _('Ask, but do not require input')),
                        ('required', _('Ask and require input')),
                    ],
                )
        for attribute in self.public_fields:
            field_name = f'cfp_public_{attribute}'
            self.fields[field_name] = forms.BooleanField(
                required=False,
                initial=obj.cfp.fields.get(attribute, default_fields()[attribute]).get('public', False),
            )

        # Add fields for custom questions
        # We use all_objects because we want to include reviewer questions and inactive questions
        # (so they can be re-activated)
        for question in exclude_session_video_from_cfp_questions(
            TalkQuestion.all_objects.filter(event=obj, is_imported=False)
        ):
            field_name = f'question_{question.pk}'
            initial = 'do_not_ask'
            if question.active:
                if question.question_required == TalkQuestionRequired.REQUIRED:
                    initial = 'required'
                else:
                    initial = 'optional'

            self.fields[field_name] = forms.ChoiceField(
                required=False,
                initial=initial,
                label=question.question,
                choices=[
                    ('do_not_ask', _('Do not ask')),
                    ('optional', _('Ask, but do not require input')),
                    ('required', _('Ask and require input')),
                ],
            )

        available_codes = [code for code, _ in obj.available_content_locales]
        choices = get_language_choices_native_with_ui_name(codes=available_codes)
        existing_codes = {c[0] for c in choices}
        for code, name in obj.available_content_locales:
            if code not in existing_codes:
                choices.append((code, name))

        self.fields['content_locales'] = forms.MultipleChoiceField(
            choices=choices,
            widget=MultipleLanguagesWidget(),
            required=False,
            initial=obj.settings.get('content_locales') or [],
        )

        self.fields['cfp_ask_session_videos'].choices = [
            ('do_not_ask', _('Do not ask')),
            ('optional', _('Ask, but do not require input')),
        ]
        self._init_session_videos_from_question()

    def _init_session_videos_from_question(self):
        question = get_session_video_question(self.instance, create=False)
        if not question:
            return
        self.fields['cfp_ask_session_videos'].initial = (
            'optional' if question.active else 'do_not_ask'
        )

    def _save_session_videos_question(self):
        visibility = self.cleaned_data.get('cfp_ask_session_videos', 'do_not_ask')

        if visibility == 'do_not_ask':
            question = get_session_video_question(self.instance, create=False)
            if question:
                question.active = False
                question.is_public = False
                question.save(update_fields=['active', 'is_public'])
            return

        question = ensure_session_video_question(self.instance)
        question.active = True
        question.is_public = True
        question.save(update_fields=['active', 'is_public'])

    def clean(self):
        cleaned_data = super().clean()
        ask_content_locale = cleaned_data.get('cfp_ask_content_locale')
        content_locales = cleaned_data.get('content_locales')

        if ask_content_locale and ask_content_locale != 'do_not_ask' and not content_locales:
            self.add_error(
                'content_locales',
                forms.ValidationError(
                    _('You must select at least one content language if the Content Locale field is active.')
                )
            )
        return cleaned_data

    def save(self, *args, **kwargs):
        # Preserve fields_config (drag-drop order) before modifying settings
        fields_config = self.instance.cfp.settings.get('fields_config')

        self.instance.cfp.settings['count_length_in'] = self.cleaned_data.get('count_length_in') or 'chars'

        # Restore fields_config after setting other values (also when it is an empty dict)
        if fields_config is not None:
            self.instance.cfp.settings['fields_config'] = fields_config

        if 'content_locales' in self.cleaned_data:
            if 'cfp_ask_content_locale' in self.cleaned_data and self.cleaned_data.get('cfp_ask_content_locale') != 'do_not_ask':
                self.instance.settings.set('content_locales', self.cleaned_data['content_locales'])

        for key in self.request_require_fields:
            if key not in self.instance.cfp.fields:
                self.instance.cfp.fields[key] = default_fields()[key]
            # Full Name is always required and cannot be changed
            if key == 'fullname':
                self.instance.cfp.fields[key]['visibility'] = 'required'
            else:
                self.instance.cfp.fields[key]['visibility'] = self.cleaned_data.get(f'cfp_ask_{key}')

        for key in self.length_fields:
            self.instance.cfp.fields[key]['min_length'] = self.cleaned_data.get(f'cfp_{key}_min_length')
            self.instance.cfp.fields[key]['max_length'] = self.cleaned_data.get(f'cfp_{key}_max_length')

        self.instance.cfp.fields['slides']['max_count'] = self.cleaned_data.get('cfp_slides_max_count') or 1
        for key in self.public_fields:
            if key in {'title', 'track', 'duration', 'fullname'}:
                self.instance.cfp.fields[key]['public'] = True
            else:
                self.instance.cfp.fields[key]['public'] = bool(self.cleaned_data.get(f'cfp_public_{key}'))

        self._save_session_videos_question()

        # Save custom questions
        for question in exclude_session_video_from_cfp_questions(
            TalkQuestion.all_objects.filter(event=self.instance, is_imported=False)
        ):
            field_name = f'question_{question.pk}'
            if field_name in self.cleaned_data:
                value = self.cleaned_data[field_name]
                if value == 'do_not_ask':
                    question.active = False
                else:
                    question.active = True
                    if value == 'required':
                        question.question_required = TalkQuestionRequired.REQUIRED
                    else:
                        question.question_required = TalkQuestionRequired.OPTIONAL
                question.save()

        super().save(*args, persist_cfp=False, update_count_length_in=False, **kwargs)
        self.instance.cfp.save(update_fields=['settings', 'fields'])


class CfPForm(ReadOnlyFlag, I18nHelpText, JsonSubfieldMixin, I18nModelForm):
    text = I18nRichTextFormField(
    required=False,
    label=_('Page content'),
    help_text=_('Enter the content using the rich-text editor.'),
    sanitizer=sanitize_rich_text,
    )
    show_deadline = forms.BooleanField(
        label=_('Display deadline publicly'),
        required=False,
        help_text=_('Show the time and date the CfP ends to potential speakers.'),
    )
    hide_after_deadline = forms.BooleanField(
        label=_('Do not show Call for Speakers on the menu after the deadline'),
        required=False,
        help_text=_(
            'If enabled, the Call for Speakers link will be hidden from navigation menus '
            'once the submission deadline has passed.'
        ),
    )

    class Meta:
        model = CfP
        fields = ['headline', 'text', 'deadline']
        widgets = {
            'deadline': HtmlDateTimeInput,
        }
        # These are JSON fields on cfp.settings
        json_fields = {
            'show_deadline': 'settings',
            'hide_after_deadline': 'settings',
        }


class TalkQuestionForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    options = forms.FileField(
        label=_('Upload options'),
        help_text=_(
            'You can upload options here, one option per line. '
            'To use multiple languages, please upload a JSON file with a list of '
            'options:'
        )
        + ' <code>[{"en": "English", "de": "Deutsch"}, ...]</code>',
        required=False,
    )
    options_replace = forms.BooleanField(
        label=_('Replace existing options'),
        help_text=_(
            'If you upload new options, do you want to replace the existing ones? '
            'Please note that this will DELETE all existing responses to this custom field! '
            'If you do not check this, the uploaded options will be added to the '
            'existing ones, without adding duplicates.'
        ),
        required=False,
    )

    def __init__(self, *args, event=None, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields['question'].required = True
        self.fields['question'].label = _('Custom question')
        if not (instance and instance.pk):
            target = self.initial.get('target')
            if target and 'target' in self.fields:
                self.initial['target'] = target
                self.fields['target'].initial = target
        if not (event.get_feature_flag('use_tracks') and event.tracks.all().count() and event.cfp.request_track):
            self.fields.pop('tracks')
        else:
            self.fields['tracks'].queryset = event.tracks.all()
        if not event.submission_types.count():
            self.fields.pop('submission_types')
        else:
            self.fields['submission_types'].queryset = event.submission_types.all()
        if instance and instance.pk and instance.answers.count() and not instance.is_public:
            self.fields['is_public'].disabled = True

        # Session video is a single auto-managed field; organisers cannot create more.
        is_existing_session_video = bool(
            instance
            and instance.pk
            and instance.variant == TalkQuestionVariant.VIDEO
            and instance.target == TalkQuestionTarget.SUBMISSION
        )
        if is_existing_session_video:
            self.fields['variant'].disabled = True
            if 'target' in self.fields:
                self.fields['target'].disabled = True
        else:
            self.fields['variant'].choices = [
                choice
                for choice in self.fields['variant'].choices
                if choice[0] != TalkQuestionVariant.VIDEO
            ]
        
        self.fields['dependency_question'].queryset = TalkQuestion.all_objects.filter(
            event=event,
            variant__in=(
                TalkQuestionVariant.BOOLEAN,
                TalkQuestionVariant.CHOICES,
                TalkQuestionVariant.MULTIPLE,
            ),
        )
        
        if instance and instance.pk:
            self.fields['dependency_question'].queryset = (
                self.fields['dependency_question'].queryset.exclude(pk=instance.pk)
            )
            if instance.target:
                self.fields['dependency_question'].queryset = (
                    self.fields['dependency_question'].queryset.filter(target=instance.target)
                )
        elif 'target' in self.initial:
            self.fields['dependency_question'].queryset = (
                self.fields['dependency_question'].queryset.filter(target=self.initial['target'])
            )
        
        self.fields['dependency_values'].required = False

    def clean_variant(self):
        variant = self.cleaned_data.get('variant')
        if variant != TalkQuestionVariant.VIDEO:
            return variant
        if self.instance and self.instance.pk and self.instance.variant == TalkQuestionVariant.VIDEO:
            return variant
        raise forms.ValidationError(
            _('The session video field is created automatically. Only one video link field is allowed.')
        )

    def clean_options(self):
        # read uploaded file, return list of strings or list of i18n strings
        options = self.cleaned_data.get('options')
        if not options:
            return
        try:
            content = options.read().decode('utf-8')
        except Exception:
            raise forms.ValidationError(_('Could not read file.'))

        try:
            options = json.loads(content)
            if not isinstance(options, list):
                raise Exception(_('JSON file does not contain a list.'))
            if not all(isinstance(opt, dict) for opt in options):
                raise Exception(_('JSON file does not contain a list of objects.'))
            return [LazyI18nString(data=opt) for opt in options]
        except Exception:
            options = content.split('\n')
            return [opt.strip() for opt in options if opt.strip()]

    def clean_dependency_values(self):
        if self.is_bound:
            return self.data.getlist(self.add_prefix('dependency_values'))
        return self.cleaned_data.get('dependency_values')

    def clean_dependency_question(self):
        dep = self.cleaned_data.get('dependency_question')
        if dep:
            seen_ids = {self.instance.pk} if self.instance else set()
            while dep:
                if dep.pk in seen_ids:
                    raise forms.ValidationError(_('Circular dependency between questions detected.'))
                seen_ids.add(dep.pk)
                dep = dep.dependency_question
        return self.cleaned_data.get('dependency_question')

    def clean(self):
        d = super().clean()
        deadline = d.get('deadline')
        question_required = d.get('question_required')
        if (not deadline) and (question_required == TalkQuestionRequired.AFTER_DEADLINE):
            self.add_error(
                'deadline',
                forms.ValidationError(_('Please select a deadline after which the field should become mandatory.')),
            )
        if question_required in (TalkQuestionRequired.OPTIONAL, TalkQuestionRequired.REQUIRED):
            d['deadline'] = None
        options = d.get('options')
        options_replace = d.get('options_replace')
        if options_replace and not options:
            self.add_error(
                'options_replace',
                forms.ValidationError(_('You cannot replace options without uploading new ones.')),
            )
        
        dependency_question = d.get('dependency_question')
        dependency_values = d.get('dependency_values')
        target = d.get('target')
        
        if dependency_question and not dependency_values:
            self.add_error('dependency_values', _('This field is required.'))
        
        if dependency_question and target and dependency_question.target != target:
            self.add_error(
                'dependency_question',
                forms.ValidationError(
                    _('The dependency field must have the same field type (per proposal/per speaker) as this field.')
                ),
            )
        
        if not dependency_question:
            d['dependency_values'] = []
        
        return d

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        options = self.cleaned_data.get('options')
        options_replace = self.cleaned_data.get('options_replace')
        if not options:
            return instance
        if options_replace:
            instance.answers.all().delete()
            instance.options.all().delete()
            for index, option in enumerate(options):
                instance.options.create(answer=option, position=index + 1)
            return instance

        # If we aren't replacing all existing options, we need to make sure
        # we don't add duplicates.
        existing_options = instance.options.all()
        use_i18n = isinstance(options[0], LazyI18nString) and instance.event.is_multilingual
        if not use_i18n:
            # Monolangual i18n strings with strings aren't equal, so we're normalising.
            with override(instance.event.locale):
                existing_options = {str(opt.answer): opt for opt in existing_options}
                options = [str(opt) for opt in options]
        else:
            existing_options = {str(opt.answer): opt for opt in existing_options}
        new_options = []
        changed_options = []
        for index, option in enumerate(options):
            if option not in existing_options:
                new_options.append(AnswerOption(question=instance, answer=option, position=index + 1))
            else:
                existing_option = existing_options[option]
                if existing_option.position != index + 1:
                    existing_option.position = index + 1
                    changed_options.append(existing_option)
        AnswerOption.objects.bulk_create(new_options)
        AnswerOption.objects.bulk_update(changed_options, ['position'])

    class Meta:
        model = TalkQuestion
        fields = [
            'target',
            'variant',
            'question',
            'help_text',
            'is_public',
            'contains_personal_data',
            'is_visible_to_reviewers',
            'tracks',
            'submission_types',
            'question_required',
            'deadline',
            'freeze_after',
            'min_length',
            'max_length',
            'min_number',
            'max_number',
            'min_date',
            'max_date',
            'min_datetime',
            'max_datetime',
            'dependency_question',
            'dependency_values',
        ]
        widgets = {
            'deadline': HtmlDateTimeInput,
            'question_required': forms.RadioSelect(),
            'freeze_after': HtmlDateTimeInput,
            'min_datetime': HtmlDateTimeInput,
            'max_datetime': HtmlDateTimeInput,
            'min_date': HtmlDateInput,
            'max_date': HtmlDateInput,
            'tracks': EnhancedSelectMultiple,
            'submission_types': EnhancedSelectMultiple,
            'dependency_values': forms.SelectMultiple,
        }
        field_classes = {
            'variant': SafeModelChoiceField,
            'tracks': SafeModelMultipleChoiceField,
            'submission_types': SafeModelMultipleChoiceField,
            'dependency_question': SafeModelChoiceField,
        }


class AnswerOptionForm(ReadOnlyFlag, I18nHelpText, I18nModelForm):
    class Meta:
        model = AnswerOption
        fields = ['answer', 'position']
        widgets = {
            'position': forms.HiddenInput,
        }


class NameRequiredMixin:
    """Mixin to ensure the name field is always marked as required in the UI."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True


class SubmissionTypeForm(NameRequiredMixin, ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name']
        qs = self.event.submission_types.all()
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if any(str(stype.name) == str(name) for stype in qs):
            raise forms.ValidationError(_('You already have a session type by this name!'))
        return name

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        if instance.pk and 'duration' in self.changed_data:
            instance.update_duration()
        return instance

    class Meta:
        model = SubmissionType
        fields = ('name', 'default_duration', 'deadline', 'requires_access_code')
        widgets = {
            'deadline': HtmlDateTimeInput,
            'default_duration': TextInputWithAddon(addon_after=_('minutes')),
        }


class TrackForm(NameRequiredMixin, ReadOnlyFlag, I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        # Set initial color for new tracks (when creating, not editing)
        instance = kwargs.get('instance')
        if not instance or not instance.pk:
            initial = dict(kwargs.get('initial') or {})
            if 'color' not in initial or not initial.get('color'):
                # Prefer an existing color on the instance (if provided) before generating a new one
                instance_color = getattr(instance, 'color', None) if instance is not None else None
                if instance_color:
                    initial['color'] = instance_color
                elif event:
                    existing_colors = {color.lower() for color in event.tracks.values_list('color', flat=True) if color}
                    try:
                        initial['color'] = generate_random_high_contrast_color(exclude_colors=existing_colors)
                    except ValueError:
                        # If we cannot generate a color, fall back to no initial color
                        pass
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            url = f'{event.cfp.urls.new_access_code}?track={self.instance.pk}'
            self.fields['requires_access_code'].help_text += ' ' + _(
                'You can create an access code <a href="{url}">here</a>.'
            ).format(url=url)

    def clean_name(self):
        name = self.cleaned_data['name']
        qs = self.event.tracks.all()
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if any(str(track.name) == str(name) for track in qs):
            raise forms.ValidationError(_('You already have a track by this name!'))
        return name

    class Meta:
        model = Track
        fields = ('name', 'description', 'color', 'requires_access_code')
        field_classes = {
            'color': ColorField,
        }


class SubmitterAccessCodeForm(forms.ModelForm):
    def __init__(self, *args, event, **kwargs):
        self.event = event
        initial = kwargs.get('initial', {})
        if not kwargs.get('instance'):
            initial['code'] = SubmitterAccessCode.generate_code()
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(event=self.event)
        if event.get_feature_flag('use_tracks'):
            self.fields['track'].queryset = Track.objects.filter(event=self.event)
        else:
            self.fields.pop('track')

    class Meta:
        model = SubmitterAccessCode
        fields = (
            'code',
            'valid_until',
            'maximum_uses',
            'track',
            'submission_type',
        )
        field_classes = {
            'track': SafeModelChoiceField,
            'submission_type': SafeModelChoiceField,
        }
        widgets = {
            'valid_until': HtmlDateTimeInput,
            'track': EnhancedSelect,
            'submission_type': EnhancedSelect,
        }


class AccessCodeSendForm(forms.Form):
    to = forms.EmailField(label=_('To'))
    subject = forms.CharField(label=phrases.base.email_subject)
    text = forms.CharField(widget=forms.Textarea(), label=phrases.base.text_body)

    def __init__(self, *args, instance, user, **kwargs):
        self.access_code = instance
        subject = _('Access code for the {event} CfP').format(event=instance.event.name)
        text = (
            str(
                _(
                    """Hi!

This is an access code for the {event} CfP."""
                ).format(event=instance.event.name)
            )
            + ' '
        )
        if instance.track:
            text += (
                str(
                    _('It will allow you to submit a proposal to the “{track}” track.').format(
                        track=instance.track.name
                    )
                )
                + ' '
            )
        else:
            text += str(_('It will allow you to submit a proposal to our CfP.')) + ' '
        if instance.valid_until:
            text += (
                str(
                    _('This access code is valid until {date}.').format(
                        date=instance.valid_until.strftime('%Y-%m-%d %H:%M')
                    )
                )
                + ' '
            )
        if instance.maximum_uses and instance.maximum_uses != 1 and instance.maximum_uses - instance.redeemed > 1:
            text += str(_('The code can be redeemed multiple times ({num}).').format(num=instance.redemptions_left))
        text += _(
            """
Please follow this URL to use the code:

  {url}

I’m looking forward to your proposal!
{name}"""
        ).format(
            url=instance.urls.cfp_url.full(),
            name=user.get_display_name(),
        )
        initial = kwargs.get('intial', {})
        initial['subject'] = f'[{instance.event.slug}] {subject}'
        initial['text'] = text
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def save(self):
        self.access_code.send_invite(
            to=self.cleaned_data['to'].strip(),
            subject=self.cleaned_data['subject'],
            text=self.cleaned_data['text'],
        )


class QuestionFilterForm(forms.Form):
    default_renderer = InlineFormRenderer

    role = forms.ChoiceField(
        choices=(
            ('', phrases.base.all_choices),
            ('accepted', _('Accepted or confirmed speakers')),
            ('confirmed', _('Confirmed speakers')),
        ),
        required=False,
        label=_('Recipients'),
        widget=EnhancedSelect,
    )
    track = SafeModelChoiceField(Track.objects.none(), required=False, widget=EnhancedSelect)
    submission_type = SafeModelChoiceField(SubmissionType.objects.none(), required=False, widget=EnhancedSelect)

    def __init__(self, *args, event, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self.fields['submission_type'].queryset = SubmissionType.objects.filter(event=event)
        if not event.get_feature_flag('use_tracks'):
            self.fields.pop('track', None)
        elif 'track' in self.fields:
            self.fields['track'].queryset = event.tracks.all()

    def get_submissions(self):
        role = self.cleaned_data['role']
        track = self.cleaned_data.get('track')
        submission_type = self.cleaned_data['submission_type']
        talks = self.event.submissions.all()
        if role == 'accepted':
            talks = talks.filter(Q(state='accepted') | Q(state='confirmed'))
        elif role == 'confirmed':
            talks = talks.filter(state='confirmed')
        if track:
            talks = talks.filter(track=track)
        if submission_type:
            talks = talks.filter(submission_type=submission_type)
        return talks

    def get_question_information(self, question):
        result = {}
        talks = self.get_submissions()
        speakers = self.event.submitters.filter(submissions__in=talks)
        answers = question.answers.filter(Q(person__in=speakers) | Q(submission__in=talks))
        result['answer_count'] = answers.count()
        result['missing_answers'] = question.missing_answers(filter_speakers=speakers, filter_talks=talks)
        if question.variant in (TalkQuestionVariant.CHOICES, TalkQuestionVariant.MULTIPLE, TalkQuestionVariant.SELECT):
            grouped_answers = (
                answers.order_by('options')
                .values('options', 'options__answer')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
        elif question.variant == TalkQuestionVariant.FILE:
            grouped_answers = [{'answer': answer, 'count': 1} for answer in answers]
        else:
            grouped_answers = answers.order_by('answer').values('answer').annotate(count=Count('id')).order_by('-count')
        result['grouped_answers'] = grouped_answers
        return result


class ReminderFilterForm(QuestionFilterForm):
    questions = SafeModelMultipleChoiceField(
        TalkQuestion.objects.none(),
        required=False,
        help_text=_('If you select no custom field, all will be used.'),
        label=phrases.cfp.custom_fields,
        widget=EnhancedSelectMultiple,
    )

    def get_question_queryset(self):
        # We want to exclude questions with "freeze after", the deadlines of which have passed
        return TalkQuestion.objects.filter(
            event=self.event,
            target__in=['speaker', 'submission'],
        ).exclude(freeze_after__lt=timezone.now())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['questions'].queryset = self.get_question_queryset()


TARGET_TO_STEP = {
    'session': 'info',
    'speaker': 'profile',
}

BUILTIN_FIELD_DEFAULTS = {
    'session': {
        'title': {
            'label': _('Proposal title'),
            'help_text': '',
        },
        'submission_type': {
            'label': _('Session type'),
            'help_text': '',
        },
        'track': {
            'label': _('Track'),
            'help_text': '',
        },
        'content_locale': {
            'label': phrases.base.language,
            'help_text': '',
        },
        'abstract': {
            'label': _('Abstract'),
            'help_text': phrases.base.use_markdown,
        },
        'description': {
            'label': _('Description'),
            'help_text': phrases.base.use_markdown,
        },
        'notes': {
            'label': _('Notes'),
            'help_text': _('These notes are meant for the organiser and won’t be made public.'),
        },
        'slot_count': {
            'label': _('Slot Count'),
            'help_text': _('How many times this session will take place.'),
        },
        'do_not_record': {
            'label': _('Don’t record this session.'),
            'help_text': '',
        },
        'image': {
            'label': _('Session image'),
            'help_text': _('Use this if you want an illustration to go with your proposal.'),
        },
        'slides': {
            'label': _('Slides'),
            'help_text': _('Upload PDF files. Only PDF is supported right now.'),
        },
        'duration': {
            'label': _('Duration'),
            'help_text': _('The duration in minutes.'),
        },
    },
    'speaker': {
        'fullname': {
            'label': _('Full name'),
            'help_text': '',
        },
        'biography': {
            'label': _('Biography'),
            'help_text': phrases.base.use_markdown,
        },
        'job_title': {
            'label': _('Job title/role'),
            'help_text': _('What is your official job title?'),
        },
        'organization': {
            'label': _('Organization'),
            'help_text': _('What organization or company do you represent?'),
        },
        'avatar': {
            'label': _('Profile picture'),
            'help_text': _(
                'We recommend uploading an image at least 400px wide. '
                'A square image works best, as we display it in a circle in several places.'
            ),
        },
        'avatar_source': {
            'label': _('Profile Picture Source'),
            'help_text': _('Please enter the name of the author or source of image and a link if applicable.'),
        },
        'avatar_license': {
            'label': _('Profile Picture License'),
            'help_text': _('Please enter the name of the license of the photo and link to it if applicable.'),
        },
        'availabilities': {
            'label': _('Availability'),
            'help_text': '',
        },
        'additional_speaker': {
            'label': _('Additional Speaker'),
            'help_text': _(
                'If you have a co-speaker, please add their email address here, and we will invite them '
                'to create an account. If you have more than one co-speaker, you can add more speakers '
                'after finishing the proposal process.'
            ),
        },
        'social_links': {
            'label': _('Social Links'),
            'help_text': '',
        },
    },
}


class CfPFieldSettingsForm(ReadOnlyFlag, I18nHelpText, I18nFormMixin, forms.Form):
    label = I18nFormField(
        label=_('Default label/text'),
        widget=I18nTextInput,
        required=False,
    )
    help_text = I18nFormField(
        label=_('Help text'),
        widget=I18nTextarea,
        required=False,
    )
    enable_gravatar = forms.BooleanField(
        label=_('Enable Gravatar'),
        help_text=_('Allow speakers to use Gravatar for their profile picture.'),
        required=False,
    )

    def __init__(self, *args, event, target, field_id, **kwargs):
        self.event = event
        self.target = target
        self.field_id = field_id
        kwargs['locales'] = self.event.locales
        super().__init__(*args, **kwargs)

        if not (self.target == 'speaker' and self.field_id == 'avatar'):
            self.fields.pop('enable_gravatar')
        else:
            self.initial['enable_gravatar'] = self.event.cfp.enable_gravatar
            self.fields['enable_gravatar'].initial = self.event.cfp.enable_gravatar

        existing_flow = self.event.cfp.settings.get('flow', {})
        field_config = self._get_existing_field_config(existing_flow)

        default_def = BUILTIN_FIELD_DEFAULTS.get(self.target, {}).get(self.field_id, {})
        default_label = default_def.get('label', '')
        default_help_text = default_def.get('help_text', '')

        initial_label = self._build_initial_i18n(field_config, 'label', default_label)
        initial_help_text = self._build_initial_i18n(field_config, 'help_text', default_help_text)

        self.initial.setdefault('label', initial_label)
        self.initial.setdefault('help_text', initial_help_text)

    def _get_existing_field_config(self, flow_data):
        if isinstance(flow_data, str) and flow_data.strip():
            try:
                flow_data = json.loads(flow_data)
            except (json.JSONDecodeError, ValueError, TypeError):
                return None
        step_key = TARGET_TO_STEP.get(self.target, self.target)
        if not isinstance(flow_data, dict):
            return None
        steps = flow_data.get('steps', {})
        step_data = None
        if isinstance(steps, dict):
            step_data = steps.get(step_key)
        elif isinstance(steps, list):
            step_data = next((s for s in steps if isinstance(s, dict) and s.get('identifier') == step_key), None)
        if not isinstance(step_data, dict):
            return None
        fields = step_data.get('fields')
        if isinstance(fields, list):
            return next((f for f in fields if isinstance(f, dict) and f.get('key') == self.field_id), None)
        elif isinstance(fields, dict):
            return fields.get(self.field_id)
        return None

    def _build_initial_i18n(self, field_config, attr, default_value):
        data = {}
        stored_value = field_config.get(attr) if field_config else None
        stored_data = None
        if isinstance(stored_value, LazyI18nString):
            stored_data = stored_value.data
        elif isinstance(stored_value, dict):
            stored_data = stored_value
        elif isinstance(stored_value, str) and stored_value:
            stored_data = {'en': stored_value}

        for locale in self.event.locales:
            if stored_data and locale in stored_data and stored_data[locale] is not None:
                data[locale] = stored_data[locale]
            else:
                with language(locale):
                    data[locale] = str(default_value) if default_value else ''
        return LazyI18nString(data)

    def _get_or_init_flow_data(self):
        flow_data = self.event.cfp.settings.get('flow')
        if isinstance(flow_data, str) and flow_data.strip():
            try:
                flow_data = json.loads(flow_data)
            except (json.JSONDecodeError, ValueError, TypeError):
                logger.warning("Malformed JSON in event.cfp.settings['flow']")
                flow_data = None

        if isinstance(flow_data, list):
            flow_data = {
                'steps': {s.get('identifier'): s for s in flow_data if isinstance(s, dict) and s.get('identifier')}
            }
        elif not isinstance(flow_data, dict):
            flow_data = {'steps': {}}
        elif 'steps' not in flow_data or not isinstance(flow_data['steps'], dict):
            if isinstance(flow_data.get('steps'), list):
                flow_data['steps'] = {
                    s.get('identifier'): s
                    for s in flow_data['steps']
                    if isinstance(s, dict) and s.get('identifier')
                }
            else:
                flow_data['steps'] = {}
        return flow_data

    def _ensure_step_data(self, flow_data):
        step_key = TARGET_TO_STEP.get(self.target, self.target)
        if step_key not in flow_data['steps'] or not isinstance(flow_data['steps'][step_key], dict):
            flow_data['steps'][step_key] = {'identifier': step_key, 'fields': []}
        return flow_data['steps'][step_key]

    def _ensure_field_entry(self, step_data):
        if 'fields' not in step_data or not isinstance(step_data['fields'], list):
            if isinstance(step_data.get('fields'), dict):
                step_data['fields'] = [
                    {'key': k, **v} if isinstance(v, dict) else {'key': k}
                    for k, v in step_data['fields'].items()
                ]
            else:
                step_data['fields'] = []
        fields_list = step_data['fields']
        field_entry = next((f for f in fields_list if isinstance(f, dict) and f.get('key') == self.field_id), None)
        if field_entry is None:
            field_entry = {'key': self.field_id}
            fields_list.append(field_entry)
        return field_entry

    def _get_dict_copy(self, val, fallback=None):
        if isinstance(val, LazyI18nString):
            return dict(val.data)
        if isinstance(val, dict):
            return dict(val)
        if isinstance(val, str) and val:
            return {'en': val}
        if isinstance(fallback, LazyI18nString):
            return dict(fallback.data)
        if isinstance(fallback, dict):
            return dict(fallback)
        if isinstance(fallback, str) and fallback:
            return {'en': fallback}
        return {}

    def reset_locale(self, locale):
        default_def = BUILTIN_FIELD_DEFAULTS.get(self.target, {}).get(self.field_id, {})
        with language(locale):
            default_label = str(default_def.get('label', '')) if default_def.get('label') else ''
            default_help_text = str(default_def.get('help_text', '')) if default_def.get('help_text') else ''

        flow_data = self._get_or_init_flow_data()
        step_data = self._ensure_step_data(flow_data)
        field_entry = self._ensure_field_entry(step_data)

        existing_label = self._get_dict_copy(field_entry.get('label'), {})
        existing_help_text = self._get_dict_copy(field_entry.get('help_text'), {})

        initial_label = self._get_dict_copy(self.initial.get('label'), {})
        initial_help_text = self._get_dict_copy(self.initial.get('help_text'), {})

        for loc, val in initial_label.items():
            if loc in self.event.locales:
                existing_label.setdefault(loc, val)
        for loc, val in initial_help_text.items():
            if loc in self.event.locales:
                existing_help_text.setdefault(loc, val)

        existing_label[locale] = default_label
        existing_help_text[locale] = default_help_text

        field_entry['label'] = existing_label
        field_entry['help_text'] = existing_help_text

        self.event.cfp.settings['flow'] = flow_data
        self.event.cfp.save(update_fields=['settings'])
        self.event.__dict__.pop('cfp_flow', None)
        return self.event.cfp

    def save(self):
        cleaned_label = self.cleaned_data.get('label')
        cleaned_help_text = self.cleaned_data.get('help_text')

        label_dict = cleaned_label.data if isinstance(cleaned_label, LazyI18nString) else (cleaned_label or {})
        help_text_dict = (
            cleaned_help_text.data if isinstance(cleaned_help_text, LazyI18nString) else (cleaned_help_text or {})
        )

        flow_data = self._get_or_init_flow_data()
        step_data = self._ensure_step_data(flow_data)
        field_entry = self._ensure_field_entry(step_data)

        existing_label = self._get_dict_copy(field_entry.get('label'), {})
        existing_help_text = self._get_dict_copy(field_entry.get('help_text'), {})

        for loc in self.event.locales:
            if loc in label_dict:
                existing_label[loc] = label_dict[loc]
            if loc in help_text_dict:
                existing_help_text[loc] = help_text_dict[loc]

        field_entry['label'] = existing_label
        field_entry['help_text'] = existing_help_text

        self.event.cfp.settings['flow'] = flow_data

        if self.target == 'speaker' and self.field_id == 'avatar' and 'enable_gravatar' in self.cleaned_data:
            self.event.cfp.settings['cfp_enable_gravatar'] = self.cleaned_data['enable_gravatar']

        self.event.cfp.save(update_fields=['settings'])
        self.event.__dict__.pop('cfp_flow', None)
        return self.event.cfp
