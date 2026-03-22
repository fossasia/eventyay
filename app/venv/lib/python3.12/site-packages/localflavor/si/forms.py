"""Slovenian specific form helpers."""

import datetime
import re

from django.forms import ValidationError
from django.forms.fields import CharField, ChoiceField, Select
from django.utils.translation import gettext_lazy as _

from .si_postalcodes import SI_POSTALCODES_CHOICES


class SIEMSOField(CharField):
    """
    A form for validating Slovenian personal identification number.

    Additionally stores gender, nationality and birthday to self.info dictionary.
    """

    default_error_messages = {
        'invalid': _('This field should contain exactly 13 digits.'),
        'date': _('The first 7 digits of the EMSO must represent a valid past date.'),
        'checksum': _('The EMSO is not valid.'),
    }
    emso_regex = re.compile(r'^(\d{2})(\d{2})(\d{3})(\d{2})(\d{3})(\d)$')

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        m = self._regex_match(value)
        day, month, year, nationality, gender, checksum = [int(i) for i in m.groups()]

        self._validate_emso(checksum, value)
        birthday = self._validate_birthday(day, month, year)

        self.info = {
            'gender': gender < 500 and 'male' or 'female',
            'birthdate': birthday,
            'nationality': nationality,
        }
        return value

    def _regex_match(self, value):
        m = self.emso_regex.match(value)
        if m is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return m

    def _validate_birthday(self, day, month, year):
        if year < 890:
            year += 2000
        else:
            year += 1000
        try:
            birthday = datetime.date(year, month, day)
        except ValueError:
            raise ValidationError(self.error_messages['date'], code='date')
        if datetime.date.today() < birthday:
            raise ValidationError(self.error_messages['date'], code='date')
        return birthday

    def _validate_emso(self, checksum, value):
        s = 0
        int_values = [int(i) for i in value]
        for a, b in zip(int_values, list(range(7, 1, -1)) * 2):
            s += a * b
        chk = s % 11
        if chk == 0:
            k = 0
        else:
            k = 11 - chk
        if k == 10 or checksum != k:
            raise ValidationError(self.error_messages['checksum'], code='checksum')


class SITaxNumberField(CharField):
    """
    Slovenian tax number field.

    Valid input is SIXXXXXXXX or XXXXXXXX where X is a number.

    http://zylla.wipos.p.lodz.pl/ut/translation.html#PZSI
    """

    default_error_messages = {
        'invalid': _('Enter a valid tax number in form SIXXXXXXXX'),
    }
    sitax_regex = re.compile(r'^(?:SI)?([1-9]\d{7})$')

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        m = self.sitax_regex.match(value)
        if m is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        value = m.groups()[0]

        # Validate Tax number
        s = 0
        int_values = [int(i) for i in value]
        for a, b in zip(int_values, range(8, 1, -1)):
            s += a * b
        chk = 11 - (s % 11)
        if chk == 10:
            chk = 0

        if int_values[-1] != chk:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value


class SIPostalCodeField(ChoiceField):
    """Slovenian post codes field."""

    def __init__(self, **kwargs):
        kwargs.setdefault('choices', SI_POSTALCODES_CHOICES)
        super().__init__(**kwargs)


class SIPostalCodeSelect(Select):
    """A Select widget that uses Slovenian postal codes as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=SI_POSTALCODES_CHOICES)
