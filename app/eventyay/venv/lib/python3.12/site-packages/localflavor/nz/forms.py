"""New Zealand specific form helpers."""
import re

from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .nz_councils import NORTH_ISLAND_COUNCIL_CHOICES, SOUTH_ISLAND_COUNCIL_CHOICES
from .nz_provinces import PROVINCE_CHOICES
from .nz_regions import REGION_CHOICES

BANK_ACCOUNT_NUMBER_RE = re.compile(r'^(\d{2})(\d{4})(\d{7})(\d{2,3})$')


class NZRegionSelect(Select):
    """A select widget with list of New Zealand regions as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGION_CHOICES)


class NZProvinceSelect(Select):
    """A select widget with list of New Zealand provinces as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=PROVINCE_CHOICES)


class NZNorthIslandCouncilSelect(Select):
    """A select widget with list of New Zealand North Island city and district councils as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=NORTH_ISLAND_COUNCIL_CHOICES)


class NZSouthIslandCouncilSelect(Select):
    """A select widget with list of New Zealand South Island city and district councils as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=SOUTH_ISLAND_COUNCIL_CHOICES)


class NZPostCodeField(RegexField):
    """A form field that validates its input as New Zealand postal code."""

    default_error_messages = {
        'invalid': _('Invalid post code.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{4}$', **kwargs)


class NZBankAccountNumberField(CharField):
    """
    A form field that validates its input as New Zealand bank account number.

    Formats:

        XX-XXXX-XXXXXXX-XX

        XX-XXXX-XXXXXXX-XXX


    Where:

    * the first two digits is the bank ID

    * the next four digits are the branch number where the account was opened

    * the next 7 digits are the account numbers

    * the last two or three digits define type of the account.

    """

    default_error_messages = {
        'invalid': _('Invalid bank account number.'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        value = re.sub(r'(\s+|-)', '', value)
        match = BANK_ACCOUNT_NUMBER_RE.search(value)
        if match:
            # normalize the last part
            last = '0%s' % match.group(4) if len(match.group(4)) == 2 else match.group(4)
            return '%s-%s-%s-%s' % (match.group(1),
                                    match.group(2), match.group(3), last)
        raise ValidationError(self.error_messages['invalid'], code='invalid')
