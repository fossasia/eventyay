"""India-specific Form helpers."""

import re

from django.core.exceptions import ImproperlyConfigured
from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .in_states import STATE_CHOICES, STATES_NORMALIZED

aadhaar_re = re.compile(r"^(?P<part1>\d{4})[-\ ]?(?P<part2>\d{4})[-\ ]?(?P<part3>\d{4})$")


class INZipCodeField(RegexField):
    """A form field that validates input as an Indian zip code, with the format XXXXXXX."""

    default_error_messages = {
        'invalid': _('Enter a zip code in the format XXXXXX or XXX XXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{3}\s?\d{3}$', **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        # Convert to "NNNNNN" if "NNN NNN" given
        value = re.sub(r'^(\d{3})\s(\d{3})$', r'\1\2', value)
        return value


class INStateField(CharField):
    """
    A form field that validates its input is a Indian state name or abbreviation.

    It normalizes the input to the standard two-letter vehicle
    registration abbreviation for the given state or union territory

    .. versionchanged:: 1.1

       Added Telangana to list of states. More details at
       https://en.wikipedia.org/wiki/Telangana#Bifurcation_of_Andhra_Pradesh

    """

    default_error_messages = {
        'invalid': _('Enter an Indian state or territory.'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        value = value.lower()
        try:
            return STATES_NORMALIZED[value.lower()]
        except KeyError:
            pass
        raise ValidationError(self.error_messages['invalid'], code='invalid')


class INAadhaarNumberField(CharField):
    """
    A form field for Aadhaar number issued by Unique Identification Authority of India (UIDAI).

    Checks the following rules to determine whether the number is valid:

        * Conforms to the XXXX XXXX XXXX format.
        * No group consists entirely of zeroes.

    Important information:

        * Aadhaar number is a proof of identity but not of citizenship.
        * Aadhaar number is issued to every resident of India including
          foreign citizens.
        * Aadhaar number is not mandatory.

    More information can be found at
    http://uidai.gov.in/what-is-aadhaar-number.html
    """

    default_error_messages = {
        'invalid': _('Enter a valid Aadhaar number in XXXX XXXX XXXX or '
                     'XXXX-XXXX-XXXX format.'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        match = re.match(aadhaar_re, value)
        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        part1, part2, part3 = match.groupdict()['part1'], match.groupdict()['part2'], match.groupdict()['part3']

        # all the parts can't be zero
        if part1 == '0000' and part2 == '0000' and part3 == '0000':
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return '%s %s %s' % (part1, part2, part3)


class INStateSelect(Select):
    """
    A Select widget that uses a list of Indian states/territories as its choices.

    .. versionchanged:: 1.1

       Added Telangana to list of states. More details at
       https://en.wikipedia.org/wiki/Telangana#Bifurcation_of_Andhra_Pradesh

    .. versionchanged:: 3.1

       Updated Indian states and union territories names and code as per iso 3166
       (https://www.iso.org/obp/ui/#iso:code:3166:IN)
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=STATE_CHOICES)


class INPANCardNumberFormField(RegexField):
    """
    A form field that accepts Indian Permanent account number(PAN) Card Number.

    Rules:
        1. It should be ten characters long.
        2. The first three characters must be any upper case alphabets.
        3. The fourth character of PAN must be one of the following characters.
            A — Association of persons (AOP)
            B — Body of individuals (BOI)
            C — Company
            F — Firm
            G — Government
            H — HUF (Hindu undivided family)
            L — Local authority
            J — Artificial juridical person
            P — Person (Individual)
            T — Trust (AOP)
        4. The fifth character is first letter of lastname of the PAN Card holder in case of Individual
            or the first letter of first name in case of non-individual.
        5. The next four-characters must be any number from 0000 to 9999.
        6. The last(tenth) character which is a check-sum character must be any upper case alphabet.

    Note:
        1. The validation of the fifth character must be done by the developer themselves,
            as this validation is out of the scope of this project.
        2. The validation for the last digit (i.e check-sum character) is not available
            in public domain, hence it is not implemented.

    More Information at:
        1. https://en.wikipedia.org/wiki/Permanent_account_number
        2. https://www.incometaxindia.gov.in/tutorials/1.permanent%20account%20number%20(pan).pdf

    .. versionadded:: 4.0
    """

    default_error_messages = {
        'invalid': _('Please enter a valid Indian PAN card number.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$', **kwargs)
