from django import forms
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _

from eventyay.base.exporters.feedback import FeedbackCSVExporter, FeedbackJSONExporter
from eventyay.base.models import Event, Feedback


class FeedbackExportForm(forms.Form):
    exporters = {'csv': FeedbackCSVExporter, 'json': FeedbackJSONExporter}

    export_format = forms.ChoiceField(
        required=True,
        label=_('Export format'),
        help_text=_('A CSV export can be opened directly in Excel and similar applications.'),
        choices=(('csv', _('CSV export')), ('json', _('JSON export'))),
        widget=forms.RadioSelect,
        initial='csv',
    )

    def __init__(self, *args, event: Event, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)

    def export_data(self) -> HttpResponse | None:
        if not Feedback.objects.filter(talk__event=self.event).exists():
            return None
        exporter = self.exporters[self.cleaned_data['export_format']](self.event)
        filename, content_type, content = exporter.render()
        return HttpResponse(
            content,
            content_type=content_type,
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )
