from django.forms import ValidationError
from django.forms.fields import CharField
from django.utils.translation import gettext_lazy as _
from stdnum.my import nric


class MyKadFormField(CharField):
    """
    A form field that validates input as a Malaysia MyKad number.

    Conforms to the YYMMDD-PB-###G or YYMMDDPB###G format
    More info: https://en.wikipedia.org/wiki/Malaysian_identity_card

    .. versionadded:: 3.0
    """

    default_error_messages = {
        'invalid': _('Invalid MyKad number.')
    }

    def clean(self, value):
        value = super().clean(value)

        if value in self.empty_values:
            return value

        if nric.is_valid(value):
            return value
        raise ValidationError(self.error_messages['invalid'], code='invalid')

    def to_python(self, value):
        value = super().to_python(value)

        if value in self.empty_values:
            return value
        return nric.compact(value)

    def prepare_value(self, value):
        value = super().prepare_value(value)
        if value is None:
            return value
        return nric.format(value)
