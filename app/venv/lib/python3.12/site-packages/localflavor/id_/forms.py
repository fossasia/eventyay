"""ID-specific Form helpers."""

import re
import time

from django.core.exceptions import ImproperlyConfigured
from django.forms import ValidationError
from django.forms.fields import CharField, Select
from django.utils.translation import gettext_lazy as _

postcode_re = re.compile(r'^[1-9]\d{4}$')
plate_re = re.compile(r'^(?P<prefix>[A-Z]{1,2}) ' +
                      r'(?P<number>\d{1,5})( (?P<suffix>([A-Z]{1,3}|[1-9][0-9]{,2})))?$')
nik_re = re.compile(r'^\d{16}$')

WOMAN_IDENTIFIER = 40


class IDPostCodeField(CharField):
    """
    An Indonesian post code field.

    http://id.wikipedia.org/wiki/Kode_pos
    """

    default_error_messages = {
        'invalid': _('Enter a valid post code'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        if not postcode_re.search(value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        if int(value) < 10110:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # 1xxx0
        if value[0] == '1' and value[4] != '0':
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return '%s' % (value,)


class IDProvinceSelect(Select):
    """A Select widget that uses a list of provinces of Indonesia as its choices."""

    def __init__(self, attrs=None):
        # Load data in memory only when it is required, see also #17275
        from .id_choices import PROVINCE_CHOICES
        super().__init__(attrs, choices=PROVINCE_CHOICES)


class IDLicensePlatePrefixSelect(Select):
    """
    A Select widget that uses a list of vehicle license plate prefix code of Indonesia as its choices.

    http://id.wikipedia.org/wiki/Tanda_Nomor_Kendaraan_Bermotor
    """

    def __init__(self, attrs=None):
        # Load data in memory only when it is required, see also #17275
        from .id_choices import LICENSE_PLATE_PREFIX_CHOICES
        super().__init__(attrs, choices=LICENSE_PLATE_PREFIX_CHOICES)


class IDLicensePlateField(CharField):
    """
    An Indonesian vehicle license plate field.

    http://id.wikipedia.org/wiki/Tanda_Nomor_Kendaraan_Bermotor

    Plus: "B 12345 12"
    """

    default_error_messages = {
        'invalid': _('Enter a valid vehicle license plate number'),
    }
    foreign_vehicles_prefixes = ('CD', 'CC')

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        plate_number = re.sub(r'\s+', ' ', value).upper()

        number, prefix, suffix = self._validate_regex_match(plate_number)
        self._validate_prefix(prefix)
        self._validate_jakarta(prefix, suffix)
        self._validate_ri(prefix, suffix)
        self._validate_number(number)

        # CD, CC and B 12345 12
        if len(number) == 5 or prefix in self.foreign_vehicles_prefixes:
            self._validate_numeric_suffix(suffix)
            self._validate_known_codes_range(number, prefix, suffix)
        else:
            self._validate_non_numeric_suffix(suffix)
        return plate_number

    def _validate_regex_match(self, plate_number):
        matches = plate_re.search(plate_number)
        if matches is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        prefix = matches.group('prefix')
        suffix = matches.group('suffix')
        number = matches.group('number')
        return number, prefix, suffix

    def _validate_number(self, number):
        # Number can't be zero.
        if number == '0':
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def _validate_known_codes_range(self, number, prefix, suffix):
        # Known codes range is 12-124
        if prefix in self.foreign_vehicles_prefixes and not (12 <= int(number) <= 124):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if len(number) == 5 and not (12 <= int(suffix) <= 124):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def _validate_numeric_suffix(self, suffix):
        # suffix must be numeric and non-empty
        if re.match(r'^\d+$', suffix) is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def _validate_non_numeric_suffix(self, suffix):
        # suffix must be non-numeric
        if suffix is not None and re.match(r'^[A-Z]{,3}$', suffix) is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def _validate_prefix(self, prefix):
        # Load data in memory only when it is required, see also #17275
        from .id_choices import LICENSE_PLATE_PREFIX_CHOICES

        # Make sure prefix is in the list of known codes.
        if prefix not in [choice[0] for choice in LICENSE_PLATE_PREFIX_CHOICES]:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def _validate_ri(self, prefix, suffix):
        # RI plates don't have suffix.
        if prefix == 'RI' and suffix is not None and suffix != '':
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def _validate_jakarta(self, prefix, suffix):
        # Only Jakarta (prefix B) can have 3 letter suffix.
        if suffix is not None and len(suffix) == 3 and prefix != 'B':
            raise ValidationError(self.error_messages['invalid'], code='invalid')


class IDNationalIdentityNumberField(CharField):
    """
    An Indonesian national identity number (NIK/KTP#) field.

    http://id.wikipedia.org/wiki/Nomor_Induk_Kependudukan

    xx.xxxx.ddmmyy.xxxx - 16 digits (excl. dots)
    notes: for women dd + 40
    """

    default_error_messages = {
        'invalid': _('Enter a valid NIK/KTP number'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        # This replacement effectively means the value is always stripped.
        value = re.sub(r'[\s.]', '', value)
        if not nik_re.search(value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        if int(value) == 0:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        year = int(value[10:12])
        month = int(value[8:10])
        day = int(value[6:8])
        # for woman, birth date is added with 40
        if day > 31:
            day -= WOMAN_IDENTIFIER

        current_year = time.localtime().tm_year
        if year < int(str(current_year)[-2:]):
            if not IDNationalIdentityNumberField._valid_nik_date(2000 + int(year), month, day):
                raise ValidationError(self.error_messages['invalid'], code='invalid')
        elif not IDNationalIdentityNumberField._valid_nik_date(1900 + int(year), month, day):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        if value[:6] == '000000' or value[12:] == '0000':
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return '%s.%s.%s.%s' % (value[:2], value[2:6], value[6:12], value[12:])

    @staticmethod
    def _valid_nik_date(year, month, day):
        try:
            t1 = (int(year), int(month), int(day), 0, 0, 0, 0, 0, -1)
            d = time.mktime(t1)
            t2 = time.localtime(d)
            if t1[:3] != t2[:3]:
                return False
            else:
                return True
        except (OverflowError, ValueError):
            return False
