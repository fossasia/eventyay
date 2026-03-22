from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _

from .utils import get_egn_birth_date


@deconstructible
class EGNValidator:
    """
    Check Bulgarian unique citizenship number (EGN) for validity.

    More details https://en.wikipedia.org/wiki/Unique_citizenship_number
    Full information in Bulgarian about algorithm is available here
    http://www.grao.bg/esgraon.html#section2
    """

    def _check_checksum(self, egn):
        weights = (2, 4, 8, 5, 10, 9, 7, 3, 6)
        try:
            checksum = sum(weight * int(digit) for weight, digit in zip(weights, egn))
            return int(egn[-1]) == checksum % 11 % 10
        except ValueError:
            return False

    def _check_valid_date(self, egn):
        try:
            return get_egn_birth_date(egn)
        except ValueError:
            return None

    def __call__(self, egn):
        if not (len(egn) == 10 and self._check_checksum(egn) and self._check_valid_date(egn)):
            raise ValidationError(_("The EGN is not valid"), code='invalid')


@deconstructible
class EIKValidator:
    """
    Check Bulgarian EIK/BULSTAT codes for validity.

    Full information in Bulgarian about algorithm is available here
    http://bulstat.registryagency.bg/About.html
    """
    error_message = _('EIK/BULSTAT is not valid')

    def __call__(self, value):
        try:
            value = list(map(int, value))
        except ValueError:
            raise ValidationError(self.error_message, code='invalid')

        if not (len(value) in [9, 13] and self._check_eik_base(value)):
            raise ValidationError(self.error_message, code='invalid')

        if len(value) == 13 and not self._check_eik_extra(value):
            raise ValidationError(self.error_message, code='invalid')

    def _get_checksum(self, weights, digits):
        checksum = sum(weight * digit for weight, digit in zip(weights, digits))
        return checksum % 11

    def _check_eik_base(self, eik):
        checksum = self._get_checksum(range(1, 9), eik)
        if checksum == 10:
            checksum = self._get_checksum(range(3, 11), eik)
        return eik[8] == checksum % 10

    def _check_eik_extra(self, eik):
        digits = eik[8:12]
        checksum = self._get_checksum((2, 7, 3, 5), digits)
        if checksum == 10:
            checksum = self._get_checksum((4, 9, 5, 7), digits)
        return eik[-1] == checksum % 10


eik_validator = EIKValidator()
egn_validator = EGNValidator()
