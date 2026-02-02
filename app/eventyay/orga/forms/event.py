import datetime as dt
from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.validators import RegexValidator
from django.forms import inlineformset_factory
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelMultipleChoiceField
from i18nfield.fields import I18nFormField, I18nTextarea
from i18nfield.forms import I18nFormMixin, I18nFormSetMixin, I18nModelForm

from eventyay.common.forms.mixins import (
    HierarkeyMixin,
    I18nHelpText,
    JsonSubfieldMixin,
    ReadOnlyFlag,
)
from eventyay.common.forms.renderers import InlineFormLabelRenderer
from eventyay.common.forms.widgets import (
    EnhancedSelect,
    EnhancedSelectMultiple,
    HtmlDateTimeInput,
    RichTextWidget,
)
from eventyay.common.text.css import validate_css
from eventyay.common.text.phrases import phrases
from eventyay.base.models import Event, EventExtraLink
from eventyay.orga.forms.widgets import HeaderSelect, MultipleLanguagesWidget
from eventyay.base.models import ReviewPhase, ReviewScore, ReviewScoreCategory

ENCRYPTED_PASSWORD_PLACEHOLDER = '*' * 24

SCHEDULE_DISPLAY_CHOICES = (
    ('grid', _('Grid')),
    ('list', _('List')),
)


class EventForm(ReadOnlyFlag, I18nHelpText, JsonSubfieldMixin, I18nModelForm):
    custom_css_text = forms.CharField(
        required=False,
        widget=forms.Textarea(),
        label='',
        help_text=_('You can type in your CSS instead of uploading it, too.'),
    )
    imprint_url = forms.URLField(
        label=_('Imprint URL'),
        help_text=_(
            'This should point e.g. to a part of your website that has your contact details and legal information.'
        ),
        required=False,
    )
    show_schedule = forms.BooleanField(
        label=_('Show schedule publicly'),
        help_text=_('Unset to hide your schedule, e.g. if you want to use the HTML export exclusively.'),
        required=False,
    )
    schedule = forms.ChoiceField(
        label=phrases.orga.event_schedule_format_label,
        choices=SCHEDULE_DISPLAY_CHOICES,
        required=True,
    )
    show_featured = forms.ChoiceField(
        label=_('Show featured sessions'),
        choices=(
            ('never', _('Never')),
            ('pre_schedule', _('Until the first schedule is released')),
            ('always', _('Always')),
        ),
        help_text=_(
            'Marking sessions as “featured” is a good way to show them before the first schedule release, or to highlight them once the schedule is visible.'
        ),
        required=True,
    )
    use_feedback = forms.BooleanField(
        label=_('Enable anonymous feedback'),
        help_text=_('Attendees will be able to send in feedback after a session is over.'),
        required=False,
    )
    export_html_on_release = forms.BooleanField(
        label=_('Generate HTML export on schedule release'),
        help_text=_('The static HTML export will be provided as a .zip archive on the schedule export page.'),
        required=False,
    )
    html_export_url = forms.URLField(
        label=_('HTML Export URL'),
        help_text=_(
            'If you publish your schedule via the HTML export, you will want the correct absolute URL to be set in various places. '
            'Please only set this value once you have published your schedule. Should end with a slash.'
        ),
        required=False,
    )
    header_pattern = forms.ChoiceField(
        label=phrases.orga.event_header_pattern_label,
        help_text=phrases.orga.event_header_pattern_help_text,
        choices=Event.HEADER_PATTERN_CHOICES,
        required=False,
        widget=HeaderSelect,
    )
    meta_noindex = forms.BooleanField(label=_('Ask search engines not to index the event pages'), required=False)

    def __init__(self, *args, **kwargs):
        self.is_administrator = kwargs.pop('is_administrator', False)
        super().__init__(*args, **kwargs)
        self.initial['custom_css_text'] = self.instance.custom_css.read().decode() if self.instance.custom_css else ''
        self.fields['show_featured'].help_text = (
            str(self.fields['show_featured'].help_text)
            + ' '
            + str(_('You can find the page <a {href}>here</a>.')).format(href=f'href="{self.instance.urls.featured}"')
        )

    def clean_custom_css(self):
        if self.cleaned_data.get('custom_css') or self.files.get('custom_css'):
            css = self.cleaned_data['custom_css'] or self.files['custom_css']
            if self.is_administrator:
                return css
            try:
                validate_css(css.read())
                return css
            except IsADirectoryError:
                self.instance.custom_css = None
                self.instance.save(update_fields=['custom_css'])
        else:
            self.instance.custom_css = None
            self.instance.save(update_fields=['custom_css'])
        return None

    def clean_custom_css_text(self):
        css = self.cleaned_data.get('custom_css_text').strip()
        if not css or self.is_administrator:
            return css
        validate_css(css)
        return css

    def clean(self):
        data = super().clean()
        return data

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        css_text = self.cleaned_data.get('custom_css_text', '')
        if css_text and 'custom_css_text' in self.changed_data:
            self.instance.custom_css.save(self.instance.slug + '.css', ContentFile(css_text))
        return result


    class Meta:
        model = Event
        fields = [
            'email',
            'custom_css',
            'featured_sessions_text',
        ]
        widgets = {
            'featured_sessions_text': RichTextWidget,
        }
        json_fields = {
            'imprint_url': 'display_settings',
            'show_schedule': 'feature_flags',
            'schedule': 'display_settings',
            'show_featured': 'feature_flags',
            'use_feedback': 'feature_flags',
            'export_html_on_release': 'feature_flags',
            'html_export_url': 'display_settings',
            'header_pattern': 'display_settings',
            'meta_noindex': 'display_settings',
        }


class MailSettingsForm(ReadOnlyFlag, I18nFormMixin, I18nHelpText, JsonSubfieldMixin, forms.Form):
    reply_to = forms.EmailField(
        label=_('Contact address'),
        help_text=_(
            'Reply-To address. If this setting is empty and you have no custom sender, your event email address will be used as Reply-To address.'
        ),
        required=False,
    )
    subject_prefix = forms.CharField(
        label=_('Mail subject prefix'),
        help_text=_('The prefix will be prepended to outgoing mail subjects in [brackets].'),
        required=False,
    )
    signature = forms.CharField(
        label=_('Mail signature'),
        help_text=str(_('Added to outgoing emails, preceded by “-- ”.')),
        required=False,
        widget=RichTextWidget,
    )
    smtp_use_custom = forms.BooleanField(
        label=_('Use custom SMTP server'),
        help_text=_('All mail related to your event will be sent over the SMTP server specified by you.'),
        required=False,
    )
    mail_from = forms.EmailField(
        label=_('Sender address'),
        help_text=_('Sender address for outgoing emails.'),
        required=False,
    )
    smtp_host = forms.CharField(label=_('Hostname'), required=False)
    smtp_port = forms.IntegerField(label=_('Port'), required=False)
    smtp_username = forms.CharField(label=_('Username'), required=False)
    smtp_password = forms.CharField(
        label=_('Password'),
        required=False,
        widget=forms.PasswordInput(
            attrs={'autocomplete': 'new-password'},
            render_value=True,
        ),
        validators=[
            RegexValidator(
                r"^[A-Za-z0-9!\"#$%&'()*+,./:;<=>?@\^_`{}|~-]+$",
                message=format_lazy(
                    _(
                        'The password contains unsupported letters. Please only use characters '
                        'A-Z, a-z, 0-9, and common special characters ({characters}).'
                    ),
                    characters=r'!"#$%%&\'()*+,-./:;<=>?@\^_`{}|~',
                ),
            )
        ],
    )
    smtp_use_tls = forms.BooleanField(
        label=_('Use STARTTLS'),
        help_text=_('Commonly enabled on port 587.'),
        required=False,
    )
    smtp_use_ssl = forms.BooleanField(label=_('Use SSL'), help_text=_('Commonly enabled on port 465.'), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields['smtp_password'].initial:
            self.fields['smtp_password'].initial = ENCRYPTED_PASSWORD_PLACEHOLDER

    def clean(self):
        data = self.cleaned_data
        if not data.get('smtp_use_custom'):
            # We don't need to validate all the rest when we don't use a custom email server
            return data

        if data.get('smtp_username'):
            # Leave password unchanged if the username is set and the password field is empty
            # or contains the encrypted password placeholder.
            # This makes it impossible to set an empty password as long as a username is set, but
            # Python's smtplib does not support password-less schemes anyway.
            password = data.get('smtp_password')
            if not password or password == ENCRYPTED_PASSWORD_PLACEHOLDER:
                data['smtp_password'] = self.initial.get('smtp_password')

        if not data.get('mail_from'):
            self.add_error(
                'mail_from',
                ValidationError(_('You have to provide a sender address if you use a custom SMTP server.')),
            )
        if data.get('smtp_use_tls') and data.get('smtp_use_ssl'):
            self.add_error(
                'smtp_use_tls',
                ValidationError(_('You can activate either SSL or STARTTLS security, but not both at the same time.')),
            )
        uses_encryption = data.get('smtp_use_tls') or data.get('smtp_use_ssl')
        localhost_names = [
            '127.0.0.1',
            '::1',
            '[::1]',
            'localhost',
            'localhost.localdomain',
        ]
        if not uses_encryption and data.get('smtp_host') not in localhost_names:
            self.add_error(
                'smtp_host',
                ValidationError(
                    _(
                        'You have to activate either SSL or STARTTLS security if you use a non-local mailserver due to data protection reasons. '
                        'Your administrator can add an instance-wide bypass. If you use this bypass, please also adjust your Privacy Policy.'
                    )
                ),
            )

    class Meta:
        json_fields = {
            'reply_to': 'mail_settings',
            'subject_prefix': 'mail_settings',
            'signature': 'mail_settings',
            'smtp_use_custom': 'mail_settings',
            'mail_from': 'mail_settings',
            'smtp_host': 'mail_settings',
            'smtp_port': 'mail_settings',
            'smtp_username': 'mail_settings',
            'smtp_password': 'mail_settings',
            'smtp_use_tls': 'mail_settings',
            'smtp_use_ssl': 'mail_settings',
        }


class ReviewSettingsForm(
    ReadOnlyFlag,
    I18nFormMixin,
    I18nHelpText,
    HierarkeyMixin,
    JsonSubfieldMixin,
    forms.Form,
):
    use_submission_comments = forms.BooleanField(
        label=_('Enable submission comments'),
        help_text=_('Allow organizers and reviewers to comment on submissions, separate from reviews.'),
        required=False,
    )
    score_mandatory = forms.BooleanField(label=_('Require a review score'), required=False)
    text_mandatory = forms.BooleanField(label=_('Require a review text'), required=False)
    score_format = forms.ChoiceField(
        label=_('Score display'),
        required=True,
        choices=(
            ('words_numbers', _('Text and score, e.g “Good (3)”')),
            ('numbers_words', _('Score and text, e.g “3 (good)”')),
            ('numbers', _('Just scores')),
            ('words', _('Just text')),
        ),
        initial='words_numbers',
        help_text=_(
            'This is how the score will look like on the review interface. The dashboard will always show numerical scores.'
        ),
        widget=forms.RadioSelect,
    )
    aggregate_method = forms.ChoiceField(
        label=_('Score aggregation method'),
        required=True,
        choices=(('median', _('Median')), ('mean', _('Average (mean)'))),
        widget=forms.RadioSelect,
    )
    review_help_text = I18nFormField(
        label=_('Help text for reviewers'),
        help_text=_('Shown at the top of each review while reviews can be created or edited.'),
        widget=RichTextWidget,
        required=False,
    )
    class Meta:
        json_fields = {
            'score_mandatory': 'review_settings',
            'text_mandatory': 'review_settings',
            'aggregate_method': 'review_settings',
            'score_format': 'review_settings',
            'use_submission_comments': 'feature_flags',
        }
        hierarkey_fields = ('review_help_text',)


class WidgetSettingsForm(JsonSubfieldMixin, forms.Form):
    show_widget_if_not_public = forms.BooleanField(
        label=_('Show the widget even if the schedule is not public'),
        help_text=_(
            'Set to allow external pages to show the schedule widget, even if the schedule is not shown here using eventyay.'
        ),
        required=False,
    )

    class Meta:
        json_fields = {'show_widget_if_not_public': 'feature_flags'}


class WidgetGenerationForm(forms.ModelForm):
    schedule_display = forms.ChoiceField(
        label=phrases.orga.event_schedule_format_label,
        choices=SCHEDULE_DISPLAY_CHOICES,
        required=True,
    )
    days = forms.MultipleChoiceField(
        label=_('Limit days'),
        choices=[],
        widget=EnhancedSelectMultiple,
        required=False,
        help_text=_('You can limit the days shown in the widget. Leave empty to show all days.'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['locale'].label = _('Widget language')
        event = self.instance
        self.fields['days'].choices = [
            (
                event.date_from + dt.timedelta(days=i),
                event.date_from + dt.timedelta(days=i),
            )
            for i in range(event.duration)
        ]

    class Meta:
        model = Event
        fields = ['locale']
        widgets = {'locale': EnhancedSelect}


class ReviewPhaseForm(I18nHelpText, I18nModelForm):
    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            self.add_error(
                'end',
                forms.ValidationError(_('The end of a phase has to be after its start.')),
            )
        return data

    class Meta:
        model = ReviewPhase
        fields = [
            'name',
            'start',
            'end',
            'can_review',
            'proposal_visibility',
            'can_see_speaker_names',
            'can_see_reviewer_names',
            'can_change_submission_state',
            'can_see_other_reviews',
            'can_tag_submissions',
            'speakers_can_change_submissions',
        ]
        widgets = {
            'start': HtmlDateTimeInput,
            'end': HtmlDateTimeInput,
        }


def strip_zeroes(value):
    if not isinstance(value, Decimal):
        return value
    value = str(value)
    return Decimal(value.rstrip('0'))


class ReviewScoreCategoryForm(I18nHelpText, I18nModelForm):
    new_scores = forms.CharField(required=False, initial='')

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        if not event or not event.get_feature_flag('use_tracks'):
            self.fields.pop('limit_tracks')
        else:
            self.fields['limit_tracks'].queryset = event.tracks.all()
        ids = self.data.get(self.prefix + '-new_scores')
        self.new_label_ids = ids.strip(',').split(',') if ids else []
        for label_id in self.new_label_ids:
            self._add_score_fields(label_id=label_id)

        self.label_fields = []
        if self.instance.id:
            scores = self.instance.scores.all()
            for score in scores:
                self.label_fields.append(
                    {
                        'score': score,
                        'label_field': score._meta.get_field('label').formfield(initial=score.label),
                        'value_field': score._meta.get_field('value').formfield(
                            initial=strip_zeroes(score.value), required=False
                        ),
                    }
                )
        for score in self.label_fields:
            score_id = score['score'].id
            self.fields[f'value_{score_id}'] = score['value_field']
            self.fields[f'label_{score_id}'] = score['label_field']

    def _add_score_fields(self, label_id):
        self.fields[f'value_{label_id}'] = ReviewScore._meta.get_field('value').formfield()
        self.fields[f'label_{label_id}'] = ReviewScore._meta.get_field('label').formfield()

    def get_label_fields(self):
        for score in self.label_fields:
            score_id = score['score'].id
            yield (self[f'value_{score_id}'], self[f'label_{score_id}'])

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        for score in self.label_fields:
            score_id = score['score'].id
            if any(f'_{score_id}' in changed for changed in self.changed_data):
                value = self.cleaned_data.get(f'value_{score_id}')
                label = self.cleaned_data.get(f'label_{score_id}')
                if value is None or value == '':
                    score['score'].delete()
                else:
                    score['score'].value = value
                    score['score'].label = label
                    score['score'].save()
        for score in self.new_label_ids:
            value = self.cleaned_data.get(f'value_{score}')
            label = self.cleaned_data.get(f'label_{score}')
            if (value is not None) and label:
                ReviewScore.objects.create(category=self.instance, value=value, label=label)
        return instance

    class Meta:
        model = ReviewScoreCategory
        fields = (
            'name',
            'is_independent',
            'weight',
            'required',
            'active',
            'limit_tracks',
        )
        field_classes = {
            'limit_tracks': SafeModelMultipleChoiceField,
        }
        widgets = {'limit_tracks': EnhancedSelectMultiple(color_field='color')}


class EventExtraLinkForm(I18nModelForm):
    default_renderer = InlineFormLabelRenderer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname in ('label', 'url'):
            if fname in self.fields:
                widget = self.fields[fname].widget
                if hasattr(widget, 'widgets'):
                    for subwidget in widget.widgets:
                        css = subwidget.attrs.get('class', '')
                        subwidget.attrs['class'] = (css + ' form-control').strip()
                css = widget.attrs.get('class', '')
                widget.attrs['class'] = (css + ' form-control').strip()

    class Meta:
        model = EventExtraLink
        fields = ['label', 'url']


class BaseEventExtraLinkFormSet(I18nFormSetMixin, forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        if event:
            kwargs['locales'] = event.locales
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(role=self.role)

    def save_new(self, form, commit=True):
        instance = super().save_new(form, commit=False)
        instance.role = self.role
        if commit:
            instance.save()
        return instance


class BaseEventFooterLinkFormSet(BaseEventExtraLinkFormSet):
    role = 'footer'


class BaseEventHeaderLinkFormSet(BaseEventExtraLinkFormSet):
    role = 'header'


EventFooterLinkFormset = inlineformset_factory(
    Event,
    EventExtraLink,
    EventExtraLinkForm,
    formset=BaseEventFooterLinkFormSet,
    can_order=False,
    can_delete=True,
    extra=0,
)
EventHeaderLinkFormset = inlineformset_factory(
    Event,
    EventExtraLink,
    EventExtraLinkForm,
    formset=BaseEventHeaderLinkFormSet,
    can_order=False,
    can_delete=True,
    extra=0,
)
