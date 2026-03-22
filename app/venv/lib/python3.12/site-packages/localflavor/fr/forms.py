"""FR-specific Form helpers"""
import re
from datetime import date

from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _
from stdnum import luhn

from .fr_department import DEPARTMENT_CHOICES_PER_REGION
from .fr_region import REGION_2016_CHOICES, REGION_CHOICES

nin_re = re.compile(
    r'^(?P<gender>[1278])(?P<year_of_birth>\d{2})(?P<month_of_birth>0[1-9]|1[0-2]|20|3[0-9]|4[0-2]|[5-9][0-9])'
    r'(?P<department_of_origin>\d{2}|2[AB])(?P<commune_of_origin>\d{3})(?P<person_unique_number>\d{3})'
    r'(?P<control_key>\d{2})$')


class FRZipCodeField(RegexField):
    """
    Validate local French zip code.

    The correct format is 'XXXXX'.
    """

    default_error_messages = {
        'invalid': _('Enter a zip code in the format XXXXX.'),
    }

    def __init__(self, **kwargs):
        kwargs.setdefault('label', _('Zip code'))
        kwargs['max_length'] = 5
        kwargs['min_length'] = 5
        super().__init__(r'^\d{5}$', **kwargs)


class FRDepartmentSelect(Select):
    """A Select widget that uses a list of FR departments as its choices."""

    def __init__(self, attrs=None):
        choices = [
            (dep[0], '%s - %s' % (dep[0], dep[1]))
            for dep in DEPARTMENT_CHOICES_PER_REGION
        ]
        super().__init__(attrs, choices=choices)


class FRRegionSelect(Select):
    """A Select widget that uses a list of FR Regions as its choices."""

    def __init__(self, attrs=None):
        choices = [
            (dep[0], '%s - %s' % (dep[0], dep[1]))
            for dep in REGION_CHOICES
        ]
        super().__init__(attrs, choices=choices)


class FRRegion2016Select(Select):
    """
    A Select widget that uses a list of France's New Regions as its choices.
    """
    def __init__(self, attrs=None):
        choices = [
            (reg[0], '%s - %s' % (reg[0], reg[1]))
            for reg in REGION_2016_CHOICES
        ]
        super().__init__(attrs, choices=choices)


class FRDepartmentField(CharField):
    """A Select Field that uses a FRDepartmentSelect widget."""

    widget = FRDepartmentSelect

    def __init__(self, **kwargs):
        kwargs.setdefault('label', _('Select Department'))
        super().__init__(**kwargs)


class FRRegionField(CharField):
    """A Select Field that uses a FRRegionSelect widget."""

    widget = FRRegionSelect

    def __init__(self, **kwargs):
        kwargs.setdefault('label', _('Select Region'))
        super().__init__(**kwargs)


class FRNationalIdentificationNumber(CharField):
    """
    Validates input as a French National Identification number.

    Validation of the Number, and checksum calculation is detailed at http://en.wikipedia.org/wiki/INSEE_code

    Complete spec of the codification is detailed here:
      - https://fr.scribd.com/document/456848429/INSEE-Guide-Identification
      - https://fr.scribd.com/document/456848431/INSEE-Codes-Pays

    .. versionadded:: 1.1
    """

    default_error_messages = {
        'invalid': _('Enter a valid French National Identification number.'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        value = value.replace(' ', '').replace('-', '')

        match = nin_re.match(value)
        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # Extract all parts of social number
        gender = match.group('gender')
        year_of_birth = match.group('year_of_birth')
        month_of_birth = match.group('month_of_birth')
        department_of_origin = match.group('department_of_origin')
        commune_of_origin = match.group('commune_of_origin')
        person_unique_number = match.group('person_unique_number')
        control_key = int(match.group('control_key'))

        # Get current year
        current_year = int(str(date.today().year)[2:])

        commune_of_origin, department_of_origin = self._clean_department_and_commune(commune_of_origin, current_year,
                                                                                     department_of_origin,
                                                                                     year_of_birth)

        if person_unique_number == '000':
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        if control_key > 97:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        control_number = int(gender + year_of_birth + month_of_birth +
                             department_of_origin.replace('A', '0').replace('B', '0') +
                             commune_of_origin + person_unique_number)
        if (97 - control_number % 97) == control_key:
            return value
        else:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def _clean_department_and_commune(self, commune_of_origin, current_year, department_of_origin, year_of_birth):
        if department_of_origin in ['20', '2A', '2B']:
            self._check_corsica(commune_of_origin, current_year, department_of_origin, year_of_birth)
        elif department_of_origin in ['97', '98']:
            self._check_overseas(commune_of_origin, current_year, department_of_origin, year_of_birth)
        elif department_of_origin == '99':
            self._check_foreign_countries(commune_of_origin, current_year, department_of_origin, year_of_birth)
        return commune_of_origin, department_of_origin

    def _check_corsica(self, commune_of_origin, current_year, department_of_origin, year_of_birth):
        """Departments number 20, 2A and 2B represent Corsica"""
        # For people born before 1976, Corsica number was 20
        if current_year < int(year_of_birth) < 76 and department_of_origin != '20':
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        # For people born from 1976, Corsica dep number is either 2A or 2B
        if (int(year_of_birth) > 75 and department_of_origin not in ['2A', '2B']):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def _check_overseas(self, commune_of_origin, current_year, department_of_origin, year_of_birth):
        """Overseas department numbers starts with 97 or 98 and are 3 digits long"""
        overseas_department_of_origin = department_of_origin + commune_of_origin[:1]
        overseas_commune_of_origin = commune_of_origin[1:]
        if department_of_origin == '97' and int(overseas_department_of_origin) not in range(971, 978):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        elif department_of_origin == '98' and int(overseas_department_of_origin) not in range(984, 989):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if int(overseas_commune_of_origin) < 1 or int(overseas_commune_of_origin) > 90:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def _check_foreign_countries(self, commune_of_origin, current_year, department_of_origin, year_of_birth):
        """
        The department_of_origin '99' is reserved for people born in a foreign country.
        In this case, commune_of_origin is the INSEE country code, must be [001-990]
        """
        if int(commune_of_origin) < 1 or int(commune_of_origin) > 990:
            raise ValidationError(self.error_messages['invalid'], code='invalid')


class FRSIRENField(CharField):
    """
    SIREN stands for "Système d'identification du répertoire des entreprises".

    It's under authority of the INSEE.
    See http://fr.wikipedia.org/wiki/Système_d'identification_du_répertoire_des_entreprises for more information.

    .. versionadded:: 1.1
    """

    r_valid = re.compile(r'^\d{9}$')
    _invalid_error_message = _('Enter a valid French SIREN number.')

    default_error_messages = {
        'invalid': _invalid_error_message,
        'max_length': _invalid_error_message,  # Overridden because the message isn't accurate.
    }

    def __init__(self, **kwargs):
        # Use max_length=11 instead of max_length=9 (from the model) to account for the spaces in the formatted value.
        kwargs["max_length"] = 11
        super().__init__(**kwargs)

    def prepare_value(self, value):
        if value is None:
            return value
        value = value.replace(' ', '').replace('-', '')
        return ' '.join((value[:3], value[3:6], value[6:]))

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        if not self.r_valid.match(value) or not luhn.is_valid(value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if value is not None:
            return value.upper().replace(' ', '').replace('-', '')
        return value


class FRSIRETField(CharField):
    """
    SIRET stands for "Système d'identification du répertoire des établissements".

    It's under authority of the INSEE.
    See http://fr.wikipedia.org/wiki/Système_d'identification_du_répertoire_des_établissements for more information.

    .. versionadded:: 1.1
    """

    r_valid = re.compile(r'^\d{14}$')
    _invalid_error_message = _('Enter a valid French SIRET number.')

    default_error_messages = {
        'invalid': _invalid_error_message,
        'max_length': _invalid_error_message,  # Overridden because the message isn't accurate.
    }

    def __init__(self, **kwargs):
        # Use max_length=17 instead of max_length=14 (from the model) to account for the spaces in the formatted value.
        kwargs["max_length"] = 17
        super().__init__(**kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        if not self.r_valid.match(value) or not luhn.is_valid(value[:9]) or \
            (value.startswith("356000000") and sum(int(x) for x in value) % 5 != 0):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return value

    def prepare_value(self, value):
        if value is None:
            return value
        value = value.replace(' ', '').replace('-', '')
        return ' '.join((value[:3], value[3:6], value[6:9], value[9:]))

    def to_python(self, value):
        value = super().to_python(value)
        if value is not None:
            return value.upper().replace(' ', '').replace('-', '')
        return value


class FRRNAField(CharField):
    """
    RNA Stands for "Répertoire National des Associations"

    It's under the authority of the French Minister of the Interior.
    See https://fr.wikipedia.org/wiki/R%C3%A9pertoire_national_des_associations for more information.

    .. versionadded:: 4.0
    """
    default_error_messages = {
        'invalid': _('Enter a valid French RNA number.'),
    }

    regex = re.compile(r'^W\d{9}$')

    def clean(self, value):
        value = super().clean(value)

        if value in self.empty_values:
            return self.empty_value

        value = value.replace(' ', '').replace('-', '').replace('.', '')

        if not self.regex.match(value):
            raise ValidationError(self.error_messages['invalid'], code=['invalid'])
        return value
