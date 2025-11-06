from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.files.uploadedfile import UploadedFile
from django.forms import CharField, FileField, RegexField, ValidationError
from django.utils.translation import gettext_lazy as _

from eventyay.common.forms.widgets import (
    ClearableBasenameFileInput,
    ImageInput,
    PasswordConfirmationInput,
    PasswordStrengthInput,
)
from eventyay.common.templatetags.filesize import filesize

IMAGE_EXTENSIONS = {
    '.png': ['image/png', '.png'],
    '.jpg': ['image/jpeg', '.jpg'],
    '.jpeg': ['image/jpeg', '.jpeg'],
    '.gif': ['image/gif', '.gif'],
    '.svg': ['image/svg+xml', '.svg'],
}


class GlobalValidator:
    def __call__(self, value):
        return validate_password(value)


class NewPasswordField(CharField):
    default_validators = [GlobalValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['widget'] = kwargs.get('widget', PasswordStrengthInput(render_value=False))
        super().__init__(*args, **kwargs)


class NewPasswordConfirmationField(CharField):
    def __init__(self, *args, **kwargs):
        kwargs['widget'] = kwargs.get(
            'widget',
            PasswordConfirmationInput(confirm_with=kwargs.pop('confirm_with', None)),
        )
        super().__init__(*args, **kwargs)


class SizeFileInput:
    """Takes the intended maximum upload size in bytes."""

    def __init__(self, *args, **kwargs):
        self.max_size = kwargs.pop('max_size', settings.FILE_UPLOAD_DEFAULT_LIMIT)
        super().__init__(*args, **kwargs)
        
        self.size_warning = self.get_size_warning(self.max_size)
        self.widget.attrs['data-maxsize'] = self.max_size
        self.widget.attrs['data-sizewarning'] = self.size_warning
        
        if self.size_warning not in (self.help_text or ''):
            self.help_text = f'{self.help_text} {self.size_warning}'.strip() if self.help_text else self.size_warning

    @staticmethod
    def get_size_warning(max_size=None, fallback=True):
        if not max_size and fallback:
            max_size = settings.FILE_UPLOAD_DEFAULT_LIMIT
        return _('Please do not upload files larger than {size}!').format(size=filesize(max_size))

    def validate(self, value):
        super().validate(value)
        if self.max_size and isinstance(value, UploadedFile) and value.size > self.max_size:
            raise ValidationError(self.size_warning)


class ExtensionFileInput:
    widget = ClearableBasenameFileInput
    extensions = {}

    def __init__(self, *args, **kwargs):
        self.extensions = kwargs.pop('extensions', None) or self.extensions or {}
        super().__init__(*args, **kwargs)
        
        if self.extensions:
            content_types = set()
            for ext in self.extensions.values():
                content_types.update(ext)
            self.widget.attrs['accept'] = ','.join(content_types)
            
            supported_formats = ', '.join(sorted(self.extensions.keys()))
            extension_help_text = _('Supported formats: {formats}').format(formats=supported_formats)
            
            if extension_help_text not in (self.help_text or ''):
                self.help_text = f'{self.help_text} {extension_help_text}'.strip() if self.help_text else extension_help_text

    def validate(self, value):
        super().validate(value)
        if value:
            filename = value.name
            extension = Path(filename).suffix.lower()
            if extension not in self.extensions.keys():
                allowed_formats = ', '.join(sorted(self.extensions.keys()))
                raise ValidationError(
                    _("The file type '{extension}' is not supported. Please upload one of the supported formats: {formats}.").format(
                        extension=extension,
                        formats=allowed_formats
                    )
                )


class SizeFileField(SizeFileInput, FileField):
    pass


class ExtensionFileField(ExtensionFileInput, SizeFileInput, FileField):
    pass


class ImageField(ExtensionFileInput, SizeFileInput, FileField):
    widget = ImageInput
    extensions = IMAGE_EXTENSIONS


class ColorField(RegexField):
    color_regex = '^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
    max_length = 7

    def __init__(self, *args, **kwargs):
        kwargs['regex'] = kwargs.get('regex', self.color_regex)
        super().__init__(*args, **kwargs)
        widget_class = self.widget.attrs.get('class', '')
        self.widget.attrs['class'] = f'{widget_class} colorpicker'.strip()
        self.widget.attrs['pattern'] = self.color_regex[1:-1]
