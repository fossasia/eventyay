from __future__ import annotations

import json
from io import StringIO

from defusedcsv import csv
from django import forms
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from i18nfield.utils import I18nJSONEncoder

from eventyay.base.models import Event
from eventyay.common.text.phrases import phrases


class ExportForm(forms.Form):
    """Form for exporting data.

    To customize how a field's value is retrieved, subclasses can define a method named `_get_{field_name}_value`.
    For example, to customize the 'title' field, define `_get_title_value`.

    As a side-note, the `get_object_attribute` method uses this convention: it looks for a method named
    `_get_{attribute}_value` and calls it if present, otherwise it accesses the attribute directly.
    """
    export_format = forms.ChoiceField(
        required=True,
        label=_('Export format'),
        help_text=_('A CSV export can be opened directly in Excel and similar applications.'),
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
        help_text=_(
            'How do you want to separate data within a single cell '
            '(for example, multiple speakers in one session/multiple sessions for one speaker)?'
        ),
        choices=(
            ('comma', _('Comma')),
            ('newline', _('Newline')),
        ),
        widget=forms.RadioSelect,
        initial='comma',
    )
    event: Event

    def __init__(self, *args, event: Event, **kwargs):
        """The ``event`` parameter is required so that we can access the event settings
        and decide which fields to add / remove.
        """
        super().__init__(*args, **kwargs)
        self.event = event
        self._build_model_fields()
        self._build_question_fields()
        if 'data_delimiter' in self.fields:
            self.fields['data_delimiter'].widget.attrs['class'] = 'hide-optional'

    @property
    def questions(self):
        raise NotImplementedError

    @property
    def filename(self):
        raise NotImplementedError

    @cached_property
    def question_field_names(self):
        return [f'question_{question.pk}' for question in self.questions]

    @cached_property
    def export_fields(self):
        return [
            forms.BoundField(self, self.fields[field], field)
            for field in self.export_field_names + self.question_field_names
        ]

    def _build_model_fields(self):
        for field in self.Meta.model_fields:
            self.fields[field] = forms.BooleanField(
                required=False,
                label=self.Meta.model._meta.get_field(field).verbose_name,
            )

    def _build_question_fields(self):
        for question in self.questions:
            self.fields[f'question_{question.pk}'] = forms.BooleanField(
                required=False,
                label=f'{phrases.base.quotation_open}{question.question}{phrases.base.quotation_close}',
            )

    def clean(self):
        data = super().clean()
        if data.get('export_format') == 'csv' and 'data_delimiter' in self.fields and not data.get('data_delimiter'):
            data['data_delimiter'] = 'comma'
        return data

    def get_object_attribute(self, obj, attribute: str):
        method = getattr(self, f'_get_{attribute}_value', None)
        if method:
            return method(obj)
        return getattr(obj, attribute, None)

    def get_data(self, queryset, fields, questions):
        data = []

        for obj in queryset.iterator(chunk_size=200):
            object_data = {}
            code = getattr(obj, 'code', None)
            if code:
                object_data['ID'] = code
            # TODO: Bad OOP design: The parent class has to know about the custom method `_prepare_object_data`
            # that the child class added. May fix in the future.
            prepare_method = getattr(self, '_prepare_object_data', None)
            if prepare_method:
                # This method mutates the input `obj`.
                prepare_method(obj)
            for field in fields:
                object_data[str(self.fields[field].label)] = self.get_object_attribute(obj, field)

            for question in questions:
                answer = self.get_answer(question, obj)
                if answer:
                    object_data[str(question.question)] = answer.answer_string
                else:
                    object_data[str(question.question)] = None

            if hasattr(self, 'get_additional_data'):
                object_data.update(**self.get_additional_data(obj))
            data.append(object_data)
        return data

    def export_data(self):
        fields = [field_name for field_name in self.export_field_names if self.cleaned_data.get(field_name)]
        questions = [question for question in self.questions if self.cleaned_data.get(f'question_{question.pk}')]
        queryset = self.get_queryset()

        # Optimize DB queries
        try:
            queryset = queryset.select_related()
        except Exception:
            pass

        try:
            queryset = queryset.prefetch_related()
        except Exception:
            pass

        # Safety limit
        if queryset.count() > 10000:
            return HttpResponse(
                "Export too large. Please narrow filters or use async export."
            ) 

        if not queryset.exists():
            return
        if self.cleaned_data.get('export_format') == 'csv':
            return self.csv_export_stream(queryset, fields, questions)

        data = self.get_data(queryset, fields, questions)

        if not data:
            return

        return self.json_export(data)

    def csv_export_stream(self, queryset, fields, questions):
        # NOTE:
        # This streaming approach reduces memory usage but does not eliminate
        # heavy database queries or high concurrency load in production.
        # A background job system (e.g., Celery) would be the proper long-term solution.
        from django_scopes import scope

        delimiters = {
            'newline': '\n',
            'comma': ', ',
        }
        delimiter = delimiters[self.cleaned_data.get('data_delimiter') or 'newline']

        field_labels = {
            field: str(self.fields[field].label)
            for field in fields
        }

        question_labels = {
            question: str(question.question)
            for question in questions
        }

        def generate():
            header = None

            with scope(event=self.event):
                for obj in queryset.iterator(chunk_size=200):
                    object_data = {}

                    code = getattr(obj, 'code', None)
                    if code:
                        object_data['ID'] = code

                    prepare_method = getattr(self, '_prepare_object_data', None)
                    if prepare_method:
                        obj = prepare_method(obj)

                    for field in fields:
                        label = field_labels[field]
                        object_data[label] = self.get_object_attribute(obj, field)

                    for question in questions:
                        label = question_labels[question]
                        answer = self.get_answer(question, obj)
                        object_data[label] = answer.answer_string if answer else None

                    if hasattr(self, 'get_additional_data'):
                        object_data.update(**self.get_additional_data(obj))

                    for key, value in object_data.items():
                        if isinstance(value, list):
                            object_data[key] = delimiter.join(
                                str(item) for item in value if item is not None
                            )

                    buffer = StringIO()
                    writer = csv.writer(buffer)

                    if header is None:
                        header = list(object_data.keys())
                        writer.writerow(header)
                        yield buffer.getvalue()
                        buffer.seek(0)
                        buffer.truncate(0)

                    row = [
                        "" if object_data.get(col) is None else object_data.get(col)
                        for col in header
                    ]
                    writer.writerow(row)
                    yield buffer.getvalue()
                    buffer.seek(0)
                    buffer.truncate(0)
 
        return StreamingHttpResponse(
            generate(),
            content_type='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{self.filename}.csv"',
                'Access-Control-Allow-Origin': '*',
            },
        )
    
    def json_export(self, data):
        content = json.dumps(data, cls=I18nJSONEncoder, indent=2)
        return HttpResponse(
            content,
            content_type='application/json; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{self.filename}.json"',
                'Access-Control-Allow-Origin': '*',
            },
        )
