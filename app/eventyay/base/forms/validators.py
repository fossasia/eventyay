from string import Formatter

from django.core.exceptions import ValidationError
from django.core.validators import BaseValidator
from django.utils.translation import gettext_lazy as _
from i18nfield.strings import LazyI18nString

from eventyay.helpers.placeholders import find_placeholders


class PlaceholderValidator(BaseValidator):
    """
    Takes list of allowed placeholders,
    validates form field by checking for placeholders,
    which are not presented in taken list.
    """

    def __init__(self, limit_value, literal_braces=False):
        super().__init__(limit_value)
        self.limit_value = limit_value
        # Set for templates rendered through escape_stray_braces(): only {placeholder} slots are
        # checked, any other brace is plain text.
        self.literal_braces = literal_braces

    def __call__(self, value):
        if isinstance(value, LazyI18nString):
            for l, v in value.data.items():
                self.__call__(v)
            return

        if self.literal_braces:
            data_placeholders = find_placeholders(value)
        else:
            # Parse like str.format_map does, so escaped braces such as {{literal}} stay literal text.
            try:
                parsed = list(Formatter().parse(value))
            except ValueError:
                raise ValidationError(
                    _('Invalid placeholder syntax: You used a different number of "{" than of "}".'),
                    code='invalid_placeholder_syntax',
                )
            data_placeholders = [
                '{%s%s%s}' % (field_name, f'!{conversion}' if conversion else '', f':{format_spec}' if format_spec else '')
                for literal_text, field_name, format_spec, conversion in parsed
                if field_name is not None
            ]
        invalid_placeholders = []
        for placeholder in data_placeholders:
            # Clean backslashes that might be added by markdown editors (e.g. {join\_online\_event})
            clean_placeholder = placeholder.replace('\\_', '_')
            if clean_placeholder not in self.limit_value:
                invalid_placeholders.append(placeholder)
        if invalid_placeholders:
            raise ValidationError(
                _('Invalid placeholder(s): %(value)s'),
                code='invalid_placeholders',
                params={
                    'value': ', '.join(
                        invalid_placeholders,
                    )
                },
            )

    def clean(self, x):
        return x
