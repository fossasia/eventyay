from django import forms
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from eventyay.common.forms.mixins import ReadOnlyFlag
from eventyay.common.forms.renderers import InlineFormRenderer
from eventyay.common.forms.widgets import RichTextWidget
from eventyay.agenda.feedback_access import get_feedback_anonymous_mode
from eventyay.base.models import Feedback


class EmojiRatingWidget(forms.RadioSelect):
    template_name = 'agenda/widgets/emoji_rating.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        for group, options, index in context['widget']['optgroups']:
            for opt in options:
                try:
                    val = int(opt['value'])
                except (TypeError, ValueError):
                    val = None
                if val in Feedback.EMOJI_RATING_MAP:
                    opt['emoji'] = Feedback.EMOJI_RATING_MAP[val][0]
                    opt['rating_label'] = Feedback.EMOJI_RATING_MAP[val][1]
                else:
                    opt['emoji'] = ''
                    opt['rating_label'] = opt['label']
        return context


class FeedbackForm(ReadOnlyFlag, forms.ModelForm):
    default_renderer = InlineFormRenderer
    parent = forms.IntegerField(required=False, widget=forms.HiddenInput())

    def __init__(self, talk, **kwargs):
        super().__init__(**kwargs)
        self.instance.talk = talk
        speakers = talk.speakers.all()
        self.fields['speaker'].queryset = speakers
        self.fields['speaker'].empty_label = _('All speakers')
        if len(speakers) == 1:
            self.fields['speaker'].widget = forms.HiddenInput()

        anonymous_mode = get_feedback_anonymous_mode(talk.event)
        if anonymous_mode == 'optional':
            self.fields['is_public'].label = _('Visible to public')
            self.fields['is_public'].help_text = _(
                'If unchecked, this feedback will only be visible to the speakers and organizers.'
            )
            self.fields['is_public'].initial = True
        elif anonymous_mode == 'always':
            self.fields['is_public'].initial = False
            self.fields['is_public'].widget = forms.HiddenInput()
        else:
            self.fields['is_public'].initial = True
            self.fields['is_public'].widget = forms.HiddenInput()

    def save(self, *args, **kwargs):
        feedback = super().save(commit=False)
        if not self.cleaned_data.get('speaker') and self.instance.talk.speakers.count() == 1:
            feedback.speaker = self.instance.talk.speakers.first()
            
        parent_id = self.cleaned_data.get('parent')
        if parent_id:
            feedback.parent_id = parent_id
            
        if kwargs.get('commit', True):
            feedback.save()
            
        return feedback

    def clean_parent(self):
        parent_id = self.cleaned_data.get('parent')
        if parent_id:
            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError):
                raise forms.ValidationError(_('Invalid parent feedback.'))
            try:
                # Scope via the talk relation to avoid cross-session replies
                # and satisfy django_scopes on Feedback queries.
                self.instance.talk.feedback.get(id=parent_id)
            except Feedback.DoesNotExist:
                raise forms.ValidationError(_('Parent feedback does not exist.'))
        return parent_id

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is not None:
            try:
                rating = int(rating)
            except (TypeError, ValueError):
                raise forms.ValidationError(_('Invalid rating selected.'))
            if rating not in Feedback.EMOJI_RATING_MAP:
                raise forms.ValidationError(_('Rating must be between 1 and 5.'))
        return rating

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('parent'):
            cleaned_data['rating'] = None
        else:
            rating = cleaned_data.get('rating')
            if rating is not None and rating not in Feedback.EMOJI_RATING_MAP:
                raise forms.ValidationError({'rating': _('Invalid rating selected.')})
        return cleaned_data

    class Meta:
        model = Feedback
        fields = ['speaker', 'rating', 'review', 'is_public']
        widgets = {
            'review': RichTextWidget(attrs={'class': 'tiptap-editor'}),
            'rating': EmojiRatingWidget(
                choices=[
                    (val, format_lazy('{emoji} {label}', emoji=emoji, label=label))
                    for val, (emoji, label) in Feedback.EMOJI_RATING_MAP.items()
                ],
                attrs={'class': 'emoji-rating-input emoji-rating-radio'},
            ),
        }
