import json

from django.utils.translation import gettext_lazy as _
from i18nfield.utils import I18nJSONEncoder

from eventyay.base.models import Feedback
from eventyay.common.exporter import BaseExporter, CSVExporterMixin


class FeedbackCSVExporter(CSVExporterMixin, BaseExporter):
    public = False
    icon = 'fa-comments'
    identifier = 'feedback.csv'
    cors = '*'
    group = 'feedback'

    @property
    def verbose_name(self):
        return _('Feedback CSV')

    @property
    def filename(self):
        return f'{self.event.slug}-feedback.csv'

    def get_data(self, **kwargs):
        fieldnames = ['session_title', 'session_code', 'speaker_name', 'rating', 'review']
        data = []
        feedbacks = Feedback.objects.filter(talk__event=self.event).select_related('talk', 'speaker')
        for feedback in feedbacks:
            data.append(
                {
                    'session_title': str(feedback.talk.title) if feedback.talk else '',
                    'session_code': feedback.talk.code if feedback.talk else '',
                    'speaker_name': feedback.speaker.get_display_name() if feedback.speaker else '',
                    'rating': feedback.rating if feedback.rating is not None else '',
                    'review': feedback.review or '',
                }
            )
        return fieldnames, data


class FeedbackJSONExporter(BaseExporter):
    public = False
    icon = 'fa-comments'
    identifier = 'feedback.json'
    cors = '*'
    group = 'feedback'

    @property
    def verbose_name(self):
        return _('Feedback JSON')

    @property
    def filename(self):
        return f'{self.event.slug}-feedback.json'

    def render(self, **kwargs):
        data = []
        feedbacks = Feedback.objects.filter(talk__event=self.event).select_related('talk', 'speaker')
        for feedback in feedbacks:
            data.append(
                {
                    'id': feedback.id,
                    'session_title': str(feedback.talk.title) if feedback.talk else '',
                    'session_code': feedback.talk.code if feedback.talk else '',
                    'speaker_name': feedback.speaker.get_display_name() if feedback.speaker else '',
                    'rating': feedback.rating,
                    'review': feedback.review or '',
                }
            )
        
        content = json.dumps(data, cls=I18nJSONEncoder)
        return self.filename, 'application/json', content
