from django import forms
from django.utils.translation import gettext_lazy as _
from django_scopes import scope
from django_scopes.forms import SafeModelChoiceField, SafeModelMultipleChoiceField

from eventyay.base.models import Submission, SubmissionStates, User
from eventyay.common.forms.widgets import EnhancedSelect, EnhancedSelectMultiple


def speaker_choice_label(speaker: User) -> str:
    return f'{speaker.fullname or _("Unnamed speaker")} ({speaker.code})'


def session_choice_label(session: Submission) -> str:
    return session.title


class SpeakerSessionAssignmentForm(forms.Form):
    add_session = forms.BooleanField(required=False, label=_('Create a new session for this speaker'))
    link_existing_session = forms.BooleanField(required=False, label=_('Link an existing session instead'))
    existing_session_id = SafeModelChoiceField(
        queryset=Submission.objects.none(), required=False, label=_('Session'), widget=EnhancedSelect
    )

    def __init__(self, *args, event, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_create = user.has_perm('base.create_submission', event)
        self.can_link = user.has_perm('base.orga_update_submission', event)
        with scope(event=event):
            self.fields['existing_session_id'].queryset = (
                event.submissions.exclude(state__in=(SubmissionStates.DELETED, SubmissionStates.DRAFT))
                .only('pk', 'title', 'code')
                .order_by('title')
            )
            self.fields['existing_session_id'].label_from_instance = session_choice_label
        if self.is_bound and not self.data.get('link_existing_session'):
            self.data = self.data.copy()
            self.data.pop('existing_session_id', None)

    def clean(self):
        data = super().clean()
        if data.get('add_session') and data.get('link_existing_session'):
            raise forms.ValidationError(_('You cannot both create a new session and link an existing session.'))
        if data.get('add_session') and not self.can_create:
            raise forms.ValidationError(_('You do not have permission to create sessions.'))
        if data.get('link_existing_session'):
            if not self.can_link:
                raise forms.ValidationError(_('You do not have permission to link sessions.'))
            if not data.get('existing_session_id') and 'existing_session_id' not in self.errors:
                self.add_error('existing_session_id', _('Please select an existing session to link.'))
        return data


class SessionSpeakersForm(forms.Form):
    speakers = SafeModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label=_('Speakers'),
        help_text=_('Select existing speakers. Remove a selection to unlink that speaker from this session.'),
        widget=EnhancedSelectMultiple,
    )

    def __init__(self, *args, event, submission, **kwargs):
        with scope(event=event):
            kwargs.setdefault('initial', {})['speakers'] = list(submission.speakers.values_list('pk', flat=True))
            super().__init__(*args, **kwargs)
            self.fields['speakers'].queryset = (
                User.objects.filter(profiles__event=event).distinct().order_by('fullname', 'pk')
            )
            self.fields['speakers'].label_from_instance = speaker_choice_label
