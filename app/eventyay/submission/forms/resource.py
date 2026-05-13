from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Resource, ResourceKind
from eventyay.base.models.resource import (
    create_slide_resource,
    delete_slide_resources,
)
from eventyay.common.forms.fields import ExtensionFileField, SizeFileField
from eventyay.common.forms.renderers import InlineFormLabelRenderer
from eventyay.common.forms.widgets import SlidesWidget


PDF_EXTENSIONS = {
    '.pdf': [
        'application/pdf',
        'application/x-pdf',
        'application/acrobat',
        'applications/vnd.pdf',
        '.pdf',
    ]
}


@dataclass(frozen=True)
class SlidesData:
    links: list[str] = field(default_factory=list)
    resources: list[object] = field(default_factory=list)
    clear_ids: set[str] = field(default_factory=set)
    kept_existing_resources: list[Resource] = field(default_factory=list)

    @property
    def has_value(self) -> bool:
        return bool(self.links or self.resources or self.kept_existing_resources)

    @property
    def total_count(self) -> int:
        return len(self.links) + len(self.resources) + len(self.kept_existing_resources)

    def serialize(self) -> dict:
        return {
            'links': self.links,
            'clear_ids': sorted(self.clear_ids),
        }


def get_slides_max_count(event) -> int:
    return event.cfp.fields.get('slides', {}).get('max_count') or 1


def is_pdf_link(value: str) -> bool:
    return Path(urlparse(value).path).suffix.lower() == '.pdf'


def save_slides_resource(submission, slides: SlidesData):
    if slides.clear_ids:
        delete_slide_resources(submission, resource_ids=slides.clear_ids)

    created_resources = []
    for link in slides.links:
        created_resources.append(create_slide_resource(submission, link=link))
    for resource_file in slides.resources:
        created_resources.append(create_slide_resource(submission, resource_file=resource_file))

    return created_resources


class SlidesField(forms.Field):
    widget = SlidesWidget

    default_error_messages = {
        'missing': _('Please provide at least one PDF link or upload at least one PDF file.'),
        'invalid_link': _('Please provide a direct PDF link.'),
        'too_many': _('You can add at most {count} slide entries.'),
    }

    def __init__(self, *args, max_items=1, **kwargs):
        kwargs.setdefault(
            'help_text',
            _('Upload PDF files and/or provide direct PDF links. Only PDF is supported right now.'),
        )
        super().__init__(*args, **kwargs)
        self.link_field = forms.URLField(required=False)
        self.resource_field = ExtensionFileField(required=False, extensions=PDF_EXTENSIONS)
        self.max_items = max_items
        self.widget.max_items = max_items
        self.existing_resources = []

    def set_max_items(self, value):
        self.max_items = value
        self.widget.max_items = value

    def clean(self, value):
        value = value or {}
        clear_ids = {str(value) for value in value.get('clear_ids', []) if value}

        cleaned_links = []
        for raw_link in value.get('links_text', '').splitlines():
            stripped_link = raw_link.strip()
            if not stripped_link:
                continue
            cleaned_link = self.link_field.clean(stripped_link)
            if not is_pdf_link(cleaned_link):
                raise ValidationError(self.error_messages['invalid_link'])
            cleaned_links.append(cleaned_link)

        cleaned_resources = []
        for uploaded_resource in value.get('resources', []):
            cleaned_resources.append(self.resource_field.clean(uploaded_resource))

        kept_existing_resources = [
            resource for resource in self.existing_resources if str(resource.pk) not in clear_ids
        ]
        slides_data = SlidesData(
            links=cleaned_links,
            resources=cleaned_resources,
            clear_ids=clear_ids,
            kept_existing_resources=kept_existing_resources,
        )

        if self.required and not slides_data.has_value:
            raise ValidationError(self.error_messages['missing'])

        if self.max_items and slides_data.total_count > self.max_items:
            raise ValidationError(self.error_messages['too_many'].format(count=self.max_items))

        return slides_data


class ResourceForm(forms.ModelForm):
    default_renderer = InlineFormLabelRenderer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = True
        self.fields['description'].widget.attrs['required'] = True

    class Meta:
        model = Resource
        fields = ['resource', 'description', 'link']
        field_classes = {'resource': SizeFileField}

    def save(self, commit=True):
        self.instance.kind = ResourceKind.GENERIC
        return super().save(commit=commit)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('DELETE'):
            return cleaned_data
        if cleaned_data.get('resource') and cleaned_data.get('link'):
            raise ValidationError(_('Please either provide a link or upload a file, you cannot do both!'))
        if not cleaned_data.get('resource') and not cleaned_data.get('link'):
            raise ValidationError(_('Please provide a link or upload a file!'))
        return cleaned_data
