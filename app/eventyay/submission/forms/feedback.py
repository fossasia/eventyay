from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.common.forms.mixins import ReadOnlyFlag
from eventyay.common.forms.renderers import InlineFormRenderer
from eventyay.common.forms.widgets import MarkdownWidget
from eventyay.base.models import Feedback


class FeedbackForm(ReadOnlyFlag, forms.ModelForm):
    default_renderer = InlineFormRenderer

    def __init__(self, talk, **kwargs):
        super().__init__(**kwargs)
        self.instance.talk = talk
        speakers = talk.speakers.all()
        self.fields['speaker'].queryset = speakers
        self.fields['speaker'].empty_label = _('All speakers')
        if len(speakers) == 1:
            self.fields['speaker'].widget = forms.HiddenInput()

    def save(self, *args, **kwargs):
        if not self.cleaned_data['speaker'] and self.instance.talk.speakers.count() == 1:
            self.instance.speaker = self.instance.talk.speakers.first()
        return super().save(*args, **kwargs)

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is not None and not (1 <= rating <= 5):
            raise forms.ValidationError(_('Rating must be between 1 and 5.'))
        return rating

    class Meta:
        model = Feedback
        fields = ['speaker', 'rating', 'review']
        widgets = {
            'review': MarkdownWidget,
            'rating': forms.RadioSelect(
                choices=[(i, str(i)) for i in range(5, 0, -1)],
                attrs={'class': 'star-rating-input'},
            ),
        }
