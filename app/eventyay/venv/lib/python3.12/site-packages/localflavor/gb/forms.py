"""GB-specific Form helpers."""

import re

from django.forms import ValidationError
from django.forms.fields import CharField, Select
from django.utils.translation import gettext_lazy as _

from .gb_regions import GB_NATIONS_CHOICES, GB_REGION_CHOICES


class GBPostcodeField(CharField):
    """
    A form field that validates its input is a UK postcode.

    The regular expression used is sourced from the schema for British Standard
    BS7666 address types: https://data.gov.uk/education-standards/sites/default/files/CL-Address-Line-Type-v3-0.pdf

    The value is uppercased and a space added in the correct place, if required.
    """

    default_error_messages = {
        'invalid': _('Enter a valid postcode.'),
    }
    outcode_pattern = '[A-PR-UWYZ]([0-9]{1,2}|([A-HIK-Y][0-9](|[0-9]|[ABEHMNPRVWXY]))|[0-9][A-HJKSTUW])'
    incode_pattern = '[0-9][ABD-HJLNP-UW-Z]{2}'
    postcode_regex = re.compile(r'^(GIR 0AA|%s %s)$' % (outcode_pattern, incode_pattern))
    space_regex = re.compile(r' *(%s)$' % incode_pattern)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        postcode = value.upper()
        # Put a single space before the incode (second part).
        postcode = self.space_regex.sub(r' \1', postcode)
        if not self.postcode_regex.search(postcode):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return postcode


class GBCountySelect(Select):
    """A Select widget that uses a list of UK Counties/Regions as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=GB_REGION_CHOICES)


class GBNationSelect(Select):
    """A Select widget that uses a list of UK Nations as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=GB_NATIONS_CHOICES)
