import datetime
import os

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile
from django.forms.utils import from_current_timezone
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from eventyay.base.forms import I18nModelForm

# Import for backwards compatibility with old import paths
from eventyay.base.forms.widgets import (  # noqa

    DatePickerWidget,
    SplitDateTimePickerWidget,
    TimePickerWidget,
)


class TolerantFormsetModelForm(I18nModelForm):
    """
    This is equivalent to a normal I18nModelForm, but works around a problem that
    arises when the form is used inside a FormSet with can_order=True and django-formset-js
    enabled. In this configuration, even empty "extra" forms might have an ORDER value
    sent and Django marks the form as empty and raises validation errors because the other
    fields have not been filled.
    """

    def has_changed(self) -> bool:
        """
        Returns True if data differs from initial. Contrary to the default
        implementation, the ORDER field is being ignored.
        """
        for name, field in self.fields.items():
            if name == 'ORDER' or name == 'id':
                continue
            prefixed_name = self.add_prefix(name)
            data_value = field.widget.value_from_datadict(self.data, self.files, prefixed_name)
            if not field.show_hidden_initial:
                initial_value = self.initial.get(name, field.initial)
                if callable(initial_value):
                    initial_value = initial_value()
            else:
                initial_prefixed_name = self.add_initial_prefix(name)
                hidden_widget = field.hidden_widget()
                try:
                    initial_value = field.to_python(
                        hidden_widget.value_from_datadict(self.data, self.files, initial_prefixed_name)
                    )
                except forms.ValidationError:
                    # Always assume data has changed if validation fails.
                    self._changed_data.append(name)
                    continue
            # We're using a private API of Django here. This is not nice, but no problem as it seems
            # like this will become a public API in future Django.
            if field._has_changed(initial_value, data_value):
                return True
        return False


def selector(values, prop):
    # Given an iterable of PropertyValue objects, this will return a
    # list of their primary keys, ordered by the primary keys of the
    # properties they belong to EXCEPT the value for the property prop2.
    # We'll see later why we need this.
    return [v.id for v in sorted(values, key=lambda v: v.prop.id) if v.prop.id != prop.id]


class ClearableBasenameFileInput(forms.ClearableFileInput):
    template_name = 'pretixbase/forms/widgets/thumbnailed_file_input.html'

    class FakeFile(File):
        def __init__(self, file):
            self.file = file

        @property
        def name(self):
            if hasattr(self.file, 'display_name'):
                return self.file.display_name
            return self.file.name

        @property
        def is_img(self):
            return any(self.file.name.lower().endswith(e) for e in ('.jpg', '.jpeg', '.png', '.gif'))

        def __str__(self):
            if hasattr(self.file, 'display_name'):
                return self.file.display_name
            return os.path.basename(self.file.name).split('.', 1)[-1]

        @property
        def url(self):
            return self.file.url

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx['widget']['value'] = self.FakeFile(value)
        ctx['widget']['cachedfile'] = None
        return ctx


class CachedFileInput(forms.ClearableFileInput):
    template_name = 'pretixbase/forms/widgets/thumbnailed_file_input.html'

    class FakeFile(File):
        def __init__(self, file):
            self.file = file

        @property
        def name(self):
            return self.file.filename

        @property
        def is_img(self):
            return any(self.file.filename.lower().endswith(e) for e in ('.jpg', '.jpeg', '.png', '.gif'))

        def __str__(self):
            return self.file.filename

        @property
        def url(self):
            return reverse('cachedfile.download', kwargs={'id': self.file.id})

    def value_from_datadict(self, data, files, name):
        from ...base.models import CachedFile

        v = super().value_from_datadict(data, files, name)
        if v is None and data.get(name + '-cachedfile'):  # An explicit "[x] clear" would be False, not None
            return CachedFile.objects.filter(id=data[name + '-cachedfile']).first()
        return v

    def get_context(self, name, value, attrs):
        from ...base.models import CachedFile

        if isinstance(value, CachedFile):
            value = self.FakeFile(value)

        ctx = super().get_context(name, value, attrs)
        ctx['widget']['value'] = value
        ctx['widget']['cachedfile'] = value.file if isinstance(value, self.FakeFile) else None
        ctx['widget']['hidden_name'] = name + '-cachedfile'
        return ctx


class SizeFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        self.max_size = kwargs.pop('max_size', None)
        super().__init__(*args, **kwargs)
        
        if self.max_size:
            size_warning = _('Please do not upload files larger than {size}!').format(
                size=SizeFileField._sizeof_fmt(self.max_size)
            )
            self.widget.attrs['data-maxsize'] = self.max_size
            self.widget.attrs['data-sizewarning'] = size_warning
            
            if size_warning not in (self.help_text or ''):
                self.help_text = f'{self.help_text} {size_warning}'.strip() if self.help_text else size_warning

    @staticmethod
    def _sizeof_fmt(num, suffix='B'):
        for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
            if abs(num) < 1024.0:
                return '%3.1f%s%s' % (num, unit, suffix)
            num /= 1024.0
        return '%.1f%s%s' % (num, 'Yi', suffix)

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)
        if isinstance(data, UploadedFile) and self.max_size and data.size > self.max_size:
            raise forms.ValidationError(
                _('Please do not upload files larger than {size}!').format(
                    size=SizeFileField._sizeof_fmt(self.max_size)
                )
            )
        return data


class ExtFileField(SizeFileField):
    widget = ClearableBasenameFileInput

    def __init__(self, *args, **kwargs):
        ext_whitelist = kwargs.pop('ext_whitelist')
        self.ext_whitelist = [i.lower() for i in ext_whitelist]
        super().__init__(*args, **kwargs)
        
        if self.ext_whitelist:
            self.widget.attrs['accept'] = ','.join(self.ext_whitelist)
            
            supported_formats = ', '.join(sorted(self.ext_whitelist))
            extension_help = _('Supported formats: {formats}').format(formats=supported_formats)
            
            if extension_help not in (self.help_text or ''):
                self.help_text = f'{self.help_text} {extension_help}'.strip() if self.help_text else extension_help

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)
        if isinstance(data, File):
            filename = data.name
            ext = os.path.splitext(filename)[1]
            ext = ext.lower()
            if ext not in self.ext_whitelist:
                supported_formats = ', '.join(sorted(self.ext_whitelist))
                raise forms.ValidationError(
                    _("The file type '{extension}' is not supported. Please upload one of the supported formats: {formats}.").format(
                        extension=ext,
                        formats=supported_formats
                    )
                )
        return data


class CachedFileField(ExtFileField):
    widget = CachedFileInput

    def to_python(self, data):
        from ...base.models import CachedFile

        if isinstance(data, CachedFile):
            return data

        return super().to_python(data)

    def bound_data(self, data, initial):
        from ...base.models import CachedFile

        if isinstance(data, File):
            if hasattr(data, '_uploaded_to'):
                return data._uploaded_to
            cf = CachedFile.objects.create(
                expires=now() + datetime.timedelta(days=1),
                date=now(),
                web_download=True,
                filename=data.name,
                type=data.content_type,
            )
            cf.file.save(data.name, data.file)
            cf.save()
            data._uploaded_to = cf
            return cf
        return super().bound_data(data, initial)

    def clean(self, *args, **kwargs):
        from ...base.models import CachedFile

        data = super().clean(*args, **kwargs)
        if isinstance(data, File):
            if hasattr(data, '_uploaded_to'):
                return data._uploaded_to
            cf = CachedFile.objects.create(
                expires=now() + datetime.timedelta(days=1),
                web_download=True,
                date=now(),
                filename=data.name,
                type=data.content_type,
            )
            cf.file.save(data.name, data.file)
            cf.save()
            data._uploaded_to = cf
            return cf
        return data


class SlugWidget(forms.TextInput):
    template_name = 'pretixcontrol/slug_widget.html'
    prefix = ''

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx['pre'] = self.prefix
        return ctx


class MultipleLanguagesWidget(forms.CheckboxSelectMultiple):
    option_template_name = 'pretixcontrol/multi_languages_widget.html'

    def optgroups(self, name, value, attrs=None):
        from eventyay.helpers.i18n_utils import get_sorted_grouped_locales
        from django.utils.translation import get_language
        from django.utils.safestring import mark_safe

        # Get the set of valid codes from the original choices
        valid_codes = set(str(c[0]) for c in self.choices)
        
        # Get structured locales (sorted by current locale)
        structured = get_sorted_grouped_locales(get_language())
        
        new_choices = []
        for item in structured:
            code = item['code']
            if code in valid_codes:
                new_choices.append((code, item['styled_name']))
            
            # Add variants if they exist and are valid options
            for variant in item.get('variants', []):
                v_code = variant['code']
                if v_code in valid_codes:
                    # Indent
                    label = mark_safe(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ {variant['name']}")
                    new_choices.append((v_code, label))

        original_choices = self.choices
        self.choices = new_choices
        try:
             return super().optgroups(name, value, attrs)
        finally:
             self.choices = original_choices


class SingleLanguageWidget(forms.Select):
    def modify(self):
        if hasattr(self, '_modified'):
            return self.choices
        from eventyay.helpers.i18n_utils import get_sorted_grouped_locales
        from django.utils.translation import get_language
        from django.utils.safestring import mark_safe

        structured = get_sorted_grouped_locales(get_language())
        valid_codes = set(str(c[0]) for c in self.choices)
        new_choices = []
        
        for item in structured:
            if item['code'] in valid_codes:
                 new_choices.append((item['code'], item['styled_name']))
            for variant in item.get('variants', []):
                if variant['code'] in valid_codes:
                     label = mark_safe(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ {variant['name']}")
                     new_choices.append((variant['code'], label))
        
        self.choices = new_choices
        self._modified = True

    def options(self, name, value, attrs=None):
        self.modify()
        return super().options(name, value, attrs)

    def optgroups(self, name, value, attrs=None):
        self.modify()
        return super().optgroups(name, value, attrs)


class SplitDateTimeField(forms.SplitDateTimeField):
    def compress(self, data_list):
        # Differs from the default implementation: If only a time is given and no date, we consider the field empty
        if data_list:
            if data_list[0] in self.empty_values:
                return None
            if data_list[1] in self.empty_values:
                raise ValidationError(self.error_messages['invalid_date'], code='invalid_date')
            result = datetime.datetime.combine(*data_list)
            return from_current_timezone(result)
        return None


class FontSelect(forms.RadioSelect):
    option_template_name = 'pretixcontrol/font_option.html'
