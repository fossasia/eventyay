from django import forms
from django.utils.translation import gettext_lazy as _

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

    def save(self):
        return self.submission.send_invite(
            to=self.cleaned_data['speaker'].strip(),
            _from=self.speaker,
        )
