import json
from datetime import timedelta

from django.utils.timezone import now
from django import forms
from django.http import HttpResponse, JsonResponse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from i18nfield.utils import I18nJSONEncoder

from eventyay.base.models import CachedFile
from eventyay.orga.tasks import run_csv_export
from eventyay.common.text.phrases import phrases


class ExportForm(forms.Form):
    export_format = forms.ChoiceField(
        required=True,
        label=_('Export format'),
        choices=(
            ('csv', _('CSV export')),
            ('json', _('JSON export')),
        ),
        widget=forms.RadioSelect,
        initial='csv',
    )

    data_delimiter = forms.ChoiceField(
        required=False,
        label=_('Data delimiter'),
        choices=(
            ('comma', _('Comma')),
            ('newline', _('Newline')),
        ),
        widget=forms.RadioSelect,
        initial='comma',
    )

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        self._build_model_fields()
        self._build_question_fields()

    # -----------------------------
    # ABSTRACT
    # -----------------------------
    @property
    def questions(self):
        raise NotImplementedError

    @property
    def filename(self):
        raise NotImplementedError

    # -----------------------------
    # FIELD BUILDING
    # -----------------------------
    @cached_property
    def question_field_names(self):
        return [f'question_{q.pk}' for q in self.questions]

    def _build_model_fields(self):
        for field in self.Meta.model_fields:
            self.fields[field] = forms.BooleanField(
                required=False,
                label=self.Meta.model._meta.get_field(field).verbose_name,
            )

    def _build_question_fields(self):
        for q in self.questions:
            self.fields[f'question_{q.pk}'] = forms.BooleanField(
                required=False,
                label=f'{phrases.base.quotation_open}{q.question}{phrases.base.quotation_close}',
            )

    # -----------------------------
    # CLEAN
    # -----------------------------
    def clean(self):
        data = super().clean()
        if data.get('export_format') == 'csv':
            data['data_delimiter'] = data.get('data_delimiter') or 'comma'
        return data

    # -----------------------------
    # DATA HELPERS
    # -----------------------------
    def get_object_attribute(self, obj, attribute):
        method = getattr(self, f'_get_{attribute}_value', None)
        if method:
            return method(obj)
        return getattr(obj, attribute, None)

    def get_data(self, queryset, fields, questions):
        data = []
        delimiter = '\n' if self.cleaned_data.get("data_delimiter") == "newline" else ', '

        for obj in queryset:
            row = {}

            # ID
            code = getattr(obj, 'code', None)
            if code:
                row['ID'] = code

            # Optional preprocessing
            prepare_method = getattr(self, '_prepare_object_data', None)
            if prepare_method:
                obj = prepare_method(obj)

            # Model fields
            for field in fields:
                value = self.get_object_attribute(obj, field)

                if isinstance(value, list):
                    value = delimiter.join(str(v) for v in value if v is not None)

                row[str(self.fields[field].label)] = value

            # Questions
            for q in questions:
                answer = self.get_answer(q, obj)
                value = answer.answer_string if answer else None
                row[str(q.question)] = value

            # Additional data
            if hasattr(self, 'get_additional_data'):
                row.update(self.get_additional_data(obj))

            data.append(row)

        return data

    # -----------------------------
    # MAIN EXPORT
    # -----------------------------
    def export_data(self):
        queryset = self.get_queryset()

        if not queryset.exists():
            return JsonResponse(
                {
                    "status": "error",
                    "message": "No data to export.",
                },
                status=400
            )

        # Extract selected fields
        fields = [f for f in self.export_field_names if self.cleaned_data.get(f)]
        questions = [q for q in self.questions if self.cleaned_data.get(f'question_{q.pk}')]

        # -------------------------
        # CSV → ASYNC (CELERY)
        # -------------------------
        if self.cleaned_data.get('export_format') == 'csv':
            cf = CachedFile.objects.create(
                web_download=False,
                date=now(),
                expires=now() + timedelta(hours=24),
            )

            run_csv_export.delay(
                self.event.id,
                str(cf.id),
                f'{self.__class__.__module__}.{self.__class__.__qualname__}',
               { 
                    "fields": fields,
                    "questions": [q.pk for q in questions],
                    "delimiter": self.cleaned_data.get("data_delimiter"),
                }
           )

            return JsonResponse(
                {
                    "status": "processing",
                    "file_id": str(cf.id),
                    "message": "Export started. Use file_id to check status.",
                },
                status=202
            )

        # -------------------------
        # JSON → SYNC
        # -------------------------
        data = self.get_data(queryset, fields, questions)

        if not data:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "No data to export.",
                },
                status=400
            )

        return self.json_export(data)

    # -----------------------------
    # JSON EXPORT
    # -----------------------------
    def json_export(self, data):
        return HttpResponse(
            json.dumps(data, cls=I18nJSONEncoder, indent=2),
            content_type='application/json; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{self.filename}.json"',
            },
        )