from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, RegexValidator
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import (
    Organizer,
    OrganizerRequest,
    OrganizerRequestAnswer,
    OrganizerRequestFieldSetting,
    OrganizerRequestQuestion,
)
from eventyay.base.organizer_request_fields import REQUEST_FIELDS
from eventyay.base.services.turnstile import TurnstileValidationMixin


def validate_request_slug(slug: str, *, exclude_request_id: int | None = None) -> str:
    RegexValidator(
        r'^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\Z',
        _('Use lowercase letters, numbers, dots and dashes, starting and ending with a letter or number.'),
    )(slug)
    Organizer._meta.get_field('slug').clean(slug, None)
    if Organizer.objects.filter(slug__iexact=slug).exists():
        raise ValidationError(_('This short form is already taken.'))
    pending = OrganizerRequest.objects.filter(slug__iexact=slug, status=OrganizerRequest.Status.PENDING)
    if exclude_request_id is not None:
        pending = pending.exclude(pk=exclude_request_id)
    if pending.exists():
        raise ValidationError(_('This short form is reserved by a pending request.'))
    return slug


class OrganizerRequestReviewForm(forms.ModelForm):
    class Meta:
        model = OrganizerRequest
        fields = ('organizer_name', 'slug')
        labels = {'organizer_name': _('Organiser name on Eventyay'), 'slug': _('Short form')}

    def clean_slug(self):
        return validate_request_slug(self.cleaned_data['slug'], exclude_request_id=self.instance.pk)


class OrganizerRequestForm(TurnstileValidationMixin, OrganizerRequestReviewForm):
    turnstile_action = 'organizer_create'
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta(OrganizerRequestReviewForm.Meta):
        fields = ('name', 'email', 'affiliation', 'events', 'organizer_name', 'slug')
        labels = {
            **OrganizerRequestReviewForm.Meta.labels,
            'name': _('Your name'),
            'email': _('Email'),
            'affiliation': _('Organisation'),
            'events': _('Events you organise'),
        }
        help_texts = {
            'email': _(
                "We'll send updates about your request here. If approved, this email gets access to "
                'the organiser account. If you already have an Eventyay account, use the same email.'
            ),
            'affiliation': _('The community, company, or university these events belong to.'),
            'events': _(
                'Name the events, what kind they are (conference, meetup, workshop), and add a link if you have one.'
            ),
            'organizer_name': _(
                'The name shown publicly on your event pages, e.g. "FOSSASIA", you can change it later.'
            ),
            'slug': _(
                'A short name used in all your web addresses. Use lowercase letters, numbers, dots and'
                " dashes only. This can't be changed later, so choose carefully."
            ),
        }

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)
        if 'events' in self.fields:
            self.fields['events'].validators.append(MaxLengthValidator(10000))
            self.fields['events'].widget.attrs['maxlength'] = 10000
        self.fields['slug'].widget.attrs['aria-describedby'] = 'id_slug_helptext slug-preview slug-status'
        self.questions = list(OrganizerRequestQuestion.objects.filter(active=True).order_by('position', 'id'))
        self.field_settings = list(OrganizerRequestFieldSetting.objects.all())
        self.question_field_names = []
        for question in self.questions:
            name = f'question_{question.pk}'
            self.fields[name] = question_field(question)
            self.question_field_names.append(name)
        self._apply_field_settings()

    def _apply_field_settings(self):
        locked = {field['key'] for field in REQUEST_FIELDS if field['locked']}
        known = {field['key'] for field in REQUEST_FIELDS}
        for row in self.field_settings:
            if row.key not in known or row.key in locked or row.key not in self.fields:
                continue
            if not row.active:
                self.fields.pop(row.key)
                continue
            self.fields[row.key].required = row.required
        items = [('field', setting) for setting in self.field_settings if setting.key in known]
        items.extend(('question', question) for question in self.questions)
        items.sort(key=lambda item: (item[1].position, 0 if item[0] == 'field' else 1, item[1].pk))
        ordered = []
        for kind, obj in items:
            name = obj.key if kind == 'field' else f'question_{obj.pk}'
            if name in self.fields and name != 'website':
                ordered.append(name)
        self.order_fields([*ordered, 'website'])
        self.request_field_names = ordered

    def visible_request_fields(self):
        return [self[name] for name in self.request_field_names]

    def save_answers(self, application: OrganizerRequest) -> None:
        for question in self.questions:
            value = self.cleaned_data.get(f'question_{question.pk}')
            if question.variant == OrganizerRequestQuestion.Variant.BOOLEAN:
                text = _('Yes') if value else _('No')
            else:
                text = (value or '').strip()
            if not text:
                OrganizerRequestAnswer.objects.filter(request=application, question=question).delete()
                continue
            OrganizerRequestAnswer.objects.update_or_create(
                request=application, question=question, defaults={'answer': text}
            )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if OrganizerRequest.objects.filter(email__iexact=email, status=OrganizerRequest.Status.PENDING).exists():
            raise ValidationError(_('There is already a pending request for this email address.'))
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('website'):
            raise ValidationError(_('Unable to submit this request.'))
        self.clean_turnstile()
        return cleaned


class OrganizerRequestRejectForm(forms.Form):
    reason = forms.CharField(label=_('Reason (optional)'), required=False, max_length=10000, widget=forms.Textarea)


def question_field(question: OrganizerRequestQuestion) -> forms.Field:
    kwargs = {'label': question.label, 'help_text': question.help_text, 'required': question.required}
    if question.variant == OrganizerRequestQuestion.Variant.TEXT:
        return forms.CharField(widget=forms.Textarea, max_length=10000, **kwargs)
    if question.variant == OrganizerRequestQuestion.Variant.URL:
        return forms.URLField(assume_scheme='https', **kwargs)
    if question.variant == OrganizerRequestQuestion.Variant.BOOLEAN:
        return forms.BooleanField(**kwargs)
    return forms.CharField(max_length=500, **kwargs)


class OrganizerRequestQuestionForm(forms.ModelForm):
    class Meta:
        model = OrganizerRequestQuestion
        fields = ('label', 'help_text', 'variant', 'required', 'active')
        help_texts = {
            'required': _('People must answer this before they can submit a request.'),
            'active': _('Inactive questions stay hidden on the public form.'),
        }
