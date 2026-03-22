"""HR-specific Form helpers."""
import datetime
import re

from django.core.exceptions import ImproperlyConfigured
from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _
from stdnum import luhn

from .hr_choices import HR_COUNTY_CHOICES, HR_LICENSE_PLATE_PREFIX_CHOICES

jmbg_re = re.compile(r'^(?P<dd>\d{2})(?P<mm>\d{2})(?P<yyy>\d{3})' +
                     r'(?P<rr>\d{2})(?P<bbb>\d{3})(?P<k>\d{1})$')
oib_re = re.compile(r'^\d{11}$')
plate_re = re.compile(r'^(?P<prefix>[A-ZČŠŽ]{2})' +
                      r'(?P<number>\d{3,4})' +
                      r'(?P<suffix>[ABCDEFGHIJKLMNOPRSTUVZ]{1,2})$')
postal_code_re = re.compile(r'^\d{5}$')
jmbag_re = re.compile(r'^601983(?P<copy>\d{1})1(?P<jmbag>\d{10})(?P<k>\d{1})$')


class HRCountySelect(Select):
    """A Select widget that uses a list of counties of Croatia as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=HR_COUNTY_CHOICES)


class HRLicensePlatePrefixSelect(Select):
    """A Select widget that uses a list of vehicle license plate prefixes of Croatia as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=HR_LICENSE_PLATE_PREFIX_CHOICES)


class HRJMBGField(CharField):
    """
    Unique Master Citizen Number (JMBG) field.

    The number is still in use in Croatia, but it is being replaced by OIB.

    Source: http://en.wikipedia.org/wiki/Unique_Master_Citizen_Number

    For who might be reimplementing:
    The "area" regular expression group is used to calculate the region where a
    person was registered. Additional validation can be implemented in
    accordance with it, however this could result in exclusion of legit
    immigrated citizens. Therefore, this field works for any ex-Yugoslavia
    country.
    """

    default_error_messages = {
        'invalid': _('Enter a valid 13 digit JMBG'),
        'date': _('Error in date segment'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        matches = jmbg_re.search(value)
        if matches is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # Make sure the date part is correct.
        dd = int(matches.group('dd'))
        mm = int(matches.group('mm'))
        yyy = int(matches.group('yyy'))
        try:
            datetime.date(yyy, mm, dd)
        except ValueError:
            raise ValidationError(self.error_messages['date'], code='date')

        # Validate checksum.
        k = matches.group('k')
        checksum = 0
        for i, j in zip(range(7, 1, -1), range(6)):
            checksum += i * (int(value[j]) + int(value[13 - i]))
        m = 11 - checksum % 11
        if m == 10:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if m == 11 and k != '0':
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if not str(m) == k:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return '%s' % (value, )


class HROIBField(RegexField):
    """
    Personal Identification Number of Croatia (OIB) field.

    http://www.oib.hr/
    """

    default_error_messages = {
        'invalid': _('Enter a valid 11 digit OIB'),
    }

    def __init__(self, min_length=11, max_length=11, **kwargs):
        super().__init__(
            r'^\d{11}$', max_length=max_length, min_length=min_length,
            **kwargs
        )

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        return '%s' % (value, )


class HRLicensePlateField(CharField):
    """
    Vehicle license plate of Croatia field.

    Normalizes to the specific format
    below. Suffix is constructed from the shared letters of the Croatian and
    English alphabets.

    Format examples:
        SB 123-A
        (but also supports more characters)
        ZG 1234-AA

    Used for standardized license plates only.
    """

    default_error_messages = {
        'invalid': _('Enter a valid vehicle license plate number'),
        'area': _('Enter a valid location code'),
        'number': _('Number part cannot be zero'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        value = re.sub(r'[\s\-]+', '', value).upper()

        matches = plate_re.search(value)
        if matches is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # Make sure the prefix is in the list of known codes.
        prefix = matches.group('prefix')
        if prefix not in [choice[0] for choice in HR_LICENSE_PLATE_PREFIX_CHOICES]:
            raise ValidationError(self.error_messages['area'], code='area')

        # Make sure the number portion is not zero.
        number = matches.group('number')
        if int(number) == 0:
            raise ValidationError(self.error_messages['number'], code='number')

        return '%s %s-%s' % (prefix, number, matches.group('suffix'))


class HRPostalCodeField(CharField):
    """
    Postal code of Croatia field.

    It consists of exactly five digits ranging from 10000 to possibly less than 60000.

    http://www.posta.hr/main.aspx?id=66
    """

    default_error_messages = {
        'invalid': _('Enter a valid 5 digit postal code'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        if not postal_code_re.search(value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # Make sure the number is in valid range.
        if not 9999 < int(value) < 60000:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return '%s' % value


class HRJMBAGField(CharField):
    """
    Unique Master Academic Citizen Number of Croatia (JMBAG) field.

    This number is used by college students and professors in Croatia.

    http://www.cap.srce.hr/IzgledX.aspx
    """

    default_error_messages = {
        'invalid': _('Enter a valid 19 digit JMBAG starting with 601983'),
        'copy': _('Card issue number cannot be zero'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        value = re.sub(r'[\-\s]', '', value)

        matches = jmbag_re.search(value)
        if matches is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # Make sure the issue number is not zero.
        if matches.group('copy') == '0':
            raise ValidationError(self.error_messages['copy'], code='copy')

        # Validate checksum using Luhn algorithm.
        if not luhn.is_valid(value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return '%s' % value
