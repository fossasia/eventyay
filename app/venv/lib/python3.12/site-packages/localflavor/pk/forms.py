"""Pakistani-specific Form helpers."""

import re

from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .pk_states import STATE_CHOICES

POSTCODE_DIGITS_RE = re.compile(r'^(\d{5})$')


class PKPostCodeField(RegexField):
    """
    Pakistani post code field.

    Assumed to be 5 digits.
    """

    default_error_messages = {
        'invalid': _('Enter a 5 digit postcode.'),
    }

    def __init__(self, **kwargs):
        super().__init__(POSTCODE_DIGITS_RE, **kwargs)


class PKStateSelect(Select):
    """A Select widget that uses a list of Pakistani states/territories as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=STATE_CHOICES)
