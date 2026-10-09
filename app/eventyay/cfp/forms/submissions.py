from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.services.speaker_invite_limits import validate_speaker_invite_rate_limit
from eventyay.common.text.phrases import phrases


class SubmissionInvitationForm(forms.Form):
    speaker = forms.EmailField(
        label=phrases.cfp.speaker_email,
        widget=forms.EmailInput(attrs={'autocomplete': 'off'}),
    )

    def __init__(self, submission, speaker, *args, **kwargs):
        self.submission = submission
        self.speaker = speaker
        super().__init__(*args, **kwargs)

    def clean_speaker(self):
        email = self.cleaned_data['speaker'].strip()
        if self.submission.has_speaker_email(email):
            raise forms.ValidationError(
                _('This speaker has already been added or invited to the proposal.')
            )
        return email

    def clean(self):
        cleaned_data = super().clean()
        if not self.submission.can_invite_co_speakers:
            raise forms.ValidationError(
                phrases.cfp.invite_limit_reached.format(count=self.submission.MAX_CO_SPEAKERS)
            )
        validate_speaker_invite_rate_limit(self.speaker)
        return cleaned_data

    def save(self):
        return self.submission.send_invite(
            to=self.cleaned_data['speaker'].strip(),
            _from=self.speaker,
        )
