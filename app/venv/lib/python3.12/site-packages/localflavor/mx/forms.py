"""Mexican-specific form helpers."""
import re

from django.forms import ValidationError
from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .mx_states import STATE_CHOICES

DATE_RE = r'\d{2}((01|03|05|07|08|10|12)(0[1-9]|[12]\d|3[01])|02(0[1-9]|[12]\d)|(04|06|09|11)(0[1-9]|[12]\d|30))'


#: This is the list of inconvenient words according to the `Anexo IV` of the
#: document described in the next link:
#: http://www.sisi.org.mx/jspsi/documentos/2005/seguimiento/06101/0610100162005_065.doc
RFC_INCONVENIENT_WORDS = [
    'BUEI', 'BUEY', 'CACA', 'CACO', 'CAGA', 'CAGO', 'CAKA', 'CAKO',
    'COGE', 'COJA', 'COJE', 'COJI', 'COJO', 'CULO', 'FETO', 'GUEY',
    'JOTO', 'KACA', 'KACO', 'KAGA', 'KAGO', 'KOGE', 'KOJO', 'KAKA',
    'KULO', 'MAME', 'MAMO', 'MEAR', 'MEAS', 'MEON', 'MION', 'MOCO',
    'MULA', 'PEDA', 'PEDO', 'PENE', 'PUTA', 'PUTO', 'QULO', 'RATA',
    'RUIN',
]

#: This is the list of inconvenient words according to the `Anexo 2` of the
#: document described in the next link:
#: http://portal.veracruz.gob.mx/pls/portal/url/ITEM/444112558A57C6E0E040A8C02E00695C
CURP_INCONVENIENT_WORDS = [
    'BACA', 'BAKA', 'BUEI', 'BUEY', 'CACA', 'CACO', 'CAGA', 'CAGO',
    'CAKA', 'CAKO', 'COGE', 'COGI', 'COJA', 'COJE', 'COJI', 'COJO',
    'COLA', 'CULO', 'FALO', 'FETO', 'GETA', 'GUEI', 'GUEY', 'JETA',
    'JOTO', 'KACA', 'KACO', 'KAGA', 'KAGO', 'KAKA', 'KAKO', 'KOGE',
    'KOGI', 'KOJA', 'KOJE', 'KOJI', 'KOJO', 'KOLA', 'KULO', 'LILO',
    'LOCA', 'LOCO', 'LOKA', 'LOKO', 'MAME', 'MAMO', 'MEAR', 'MEAS',
    'MEON', 'MIAR', 'MION', 'MOCO', 'MOKO', 'MULA', 'MULO', 'NACA',
    'NACO', 'PEDA', 'PEDO', 'PENE', 'PIPI', 'PITO', 'POPO', 'PUTA',
    'PUTO', 'QULO', 'RATA', 'ROBA', 'ROBE', 'ROBO', 'RUIN', 'SENO',
    'TETA', 'VAGA', 'VAGO', 'VAKA', 'VUEI', 'VUEY', 'WUEI', 'WUEY',
]


class MXStateSelect(Select):
    """A Select widget that uses a list of Mexican states as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=STATE_CHOICES)


class MXZipCodeField(RegexField):
    """
    A form field that accepts a Mexican Zip Code.

    More info about this:
        http://en.wikipedia.org/wiki/List_of_postal_codes_in_Mexico
    """

    default_error_messages = {
        'invalid': _('Enter a valid zip code in the format XXXXX.'),
    }

    def __init__(self, **kwargs):
        zip_code_re = r'^(0[1-9]|[1][0-6]|[2-9]\d)(\d{3})$'
        super().__init__(zip_code_re, **kwargs)


class MXRFCField(RegexField):
    """
    A form field that validates a Mexican *Registro Federal de Contribuyentes*.

    Validates either `Persona física` or `Persona moral`.
    The Persona física RFC string is integrated by a juxtaposition of
    characters following the next pattern:

        =====  ======  ===========================================
        Index  Format  Accepted Characters
        =====  ======  ===========================================
        1      X       Any letter
        2      X       Any vowel
        3-4    XX      Any letter
        5-10   YYMMDD  Any valid date
        11-12  XX      Any letter or number between 0 and 9
        13     X       Any digit between 0 and 9 or the letter *A*
        =====  ======  ===========================================

    The Persona moral RFC string is integrated by a juxtaposition of
    characters following the next pattern:

        =====  ======  ============================================
        Index  Format  Accepted Characters
        =====  ======  ============================================
        1-3    XXX     Any letter including *&* and *Ñ* chars
        4-9    YYMMDD  Any valid date
        10-11  XX      Any letter or number between 0 and 9
        12     X       Any number between 0 and 9 or the letter *A*
        =====  ======  ============================================

    More info about this:
        http://es.wikipedia.org/wiki/Registro_Federal_de_Contribuyentes_(M%C3%A9xico)
    """

    default_error_messages = {
        'invalid': _('Enter a valid RFC.'),
        'invalid_checksum': _('Invalid checksum for RFC.'),
    }

    def __init__(self, min_length=12, max_length=13, **kwargs):
        rfc_re = re.compile(r'^([A-Z&Ññ]{3}|[A-Z][AEIOU][A-Z]{2})%s[A-Z0-9]{2}[0-9A]$' % DATE_RE,
                            re.IGNORECASE)
        super().__init__(rfc_re, min_length=min_length, max_length=max_length, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        value = value.upper()
        if self._has_homoclave(value):
            if not value[-1] == self._checksum(value[:-1]):
                raise ValidationError(self.error_messages['invalid_checksum'], code='invalid_checksum')
        if self._has_inconvenient_word(value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return value

    def _has_homoclave(self, rfc):
        """
        This check is done due to the existance of RFCs without a *homoclave*.

        Since the current algorithm to calculate it had not been created for
        the first RFCs ever in Mexico.
        """
        rfc_without_homoclave_re = re.compile(r'^[A-Z&Ññ]{3,4}%s$' % DATE_RE,
                                              re.IGNORECASE)
        return not rfc_without_homoclave_re.match(rfc)

    def _checksum(self, rfc):
        """
        Checksum.

        More info about this procedure:
            www.sisi.org.mx/jspsi/documentos/2005/seguimiento/06101/0610100162005_065.doc
        """
        chars = '0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ-Ñ'
        if len(rfc) == 11:
            rfc = '-' + rfc

        sum_ = sum(i * chars.index(c)
                   for i, c in zip(reversed(range(14)), rfc))
        checksum = 11 - sum_ % 11

        if checksum == 10:
            return 'A'
        elif checksum == 11:
            return '0'

        return str(checksum)

    def _has_inconvenient_word(self, rfc):
        first_four = rfc[:4]
        return first_four in RFC_INCONVENIENT_WORDS


class MXCLABEField(RegexField):
    """
    This field validates a CLABE (Clave Bancaria Estandarizada).

    A CLABE is a 18-digits long number. The first 6 digits denote bank and branch number.
    The remaining 12 digits denote an account number, plus a verifying digit.

    More info:
    https://en.wikipedia.org/wiki/CLABE

    .. versionadded:: 1.4
    """

    default_error_messages = {
        'invalid': _('Enter a valid CLABE.'),
        'invalid_checksum': _('Invalid checksum for CLABE.'),
    }

    def __init__(self, min_length=18, max_length=18, **kwargs):
        clabe_re = r'^\d{18}$'
        super().__init__(clabe_re, min_length=min_length, max_length=max_length, **kwargs)

    def _checksum(self, value):
        verification_digit = int(value[-1])
        number = value[:-1]

        weight_factor = (3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7)

        sum_remainder = sum(x * int(y) % 10 for x, y in zip(weight_factor, number)) % 10

        return verification_digit == (10 - sum_remainder) % 10

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        if not value.isdigit():
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if not self._checksum(value):
            raise ValidationError(self.error_messages['invalid_checksum'], code='invalid_checksum')

        return value


class MXCURPField(RegexField):
    """
    A field that validates a Mexican Clave Única de Registro de Población.

    The CURP is integrated by a juxtaposition of characters following the next
    pattern:

        =====  ======  ===================================================
        Index  Format  Accepted Characters
        =====  ======  ===================================================
        1      X       Any letter
        2      X       Any vowel
        3-4    XX      Any letter
        5-10   YYMMDD  Any valid date
        11     X       Either `H` or `M`, depending on the person's gender
        12-13  XX      Any valid acronym for a state in Mexico
        14-16  XXX     Any consonant
        17     X       Any number between 0 and 9 or any letter
        18     X       Any number between 0 and 9
        =====  ======  ===================================================

    More info about this:
        http://www.condusef.gob.mx/index.php/clave-unica-de-registro-de-poblacion-curp
    """

    default_error_messages = {
        'invalid': _('Enter a valid CURP.'),
        'invalid_checksum': _('Invalid checksum for CURP.'),
    }

    def __init__(self, min_length=18, max_length=18, **kwargs):
        states_re = r'(AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|' \
                    r'MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)'
        consonants_re = r'[B-DF-HJ-NP-TV-Z]'
        curp_re = (r'^[A-Z][AEIOUX][A-Z]{2}%s[HM]%s%s{3}[0-9A-Z]\d$' %
                   (DATE_RE, states_re, consonants_re))
        curp_re = re.compile(curp_re, re.IGNORECASE)
        super().__init__(curp_re, min_length=min_length, max_length=max_length, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        value = value.upper()
        if value[-1] != self._checksum(value[:-1]):
            raise ValidationError(self.error_messages['invalid_checksum'], code='invalid_checksum')
        if self._has_inconvenient_word(value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return value

    def _checksum(self, value):
        chars = '0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ'

        s = sum(i * chars.index(c) for i, c in zip(reversed(range(19)), value))
        checksum = 10 - s % 10

        if checksum == 10:
            return '0'
        return str(checksum)

    def _has_inconvenient_word(self, curp):
        first_four = curp[:4]
        return first_four in CURP_INCONVENIENT_WORDS


class MXSocialSecurityNumberField(RegexField):
    """
    A field that validates a Mexican Social Security Number.

    The Social Security Number is integrated by a juxtaposition of digits
    following the next pattern:

    =====  ==================================================================
    Index  Required numbers
    =====  ==================================================================
    1-2    The number of the branch office where the Social Security Number
           was designated.
    3-4    The year of inscription to the Social Security.
    5-6    The year of birth of the Social Security Number owner.
    7-10   The progressive number of procedure for the IMSS.
           (This digit is provided exclusively by the Institute as it regards
           the Folio number of such procedure).
    11     The verification digit.
    =====  ==================================================================

    """

    default_error_messages = {
        'invalid': _('Enter a valid Social Security Number.'),
        'invalid_checksum': _('Invalid checksum for Social Security Number.'),
    }

    def __init__(self, min_length=11, max_length=11, **kwargs):
        ssn_re = r'^\d{11}$'
        ssn_re = re.compile(ssn_re)
        super().__init__(ssn_re, min_length=min_length, max_length=max_length, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        if value[-1] != self.__checksum(value[:-1]):
            raise ValidationError(self.error_messages['invalid_checksum'], code='invalid_checksum')
        return value

    def __checksum(self, value):
        multipliers = [1 if i % 2 == 0 else 2 for i in range(10)]

        s = [int(v) * m for v, m in zip(value, multipliers)]
        s = sum(map(int, ''.join(map(str, s))))
        checksum = 10 - s % 10

        if checksum == 10:
            return '0'
        return str(checksum)
