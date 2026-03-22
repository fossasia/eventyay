from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


class NLZipCodeFieldValidator(RegexValidator):
    """
    Validation for Dutch zip codes.

    .. versionadded:: 1.3
    """

    error_message = _('Enter a valid zip code.')

    def __init__(self):
        super().__init__(regex=r'^\d{4} ?[A-Z]{2}$', message=self.error_message)

    def __call__(self, value):
        super().__call__(value)

        if int(value[:4]) < 1000:
            raise ValidationError(self.error_message, code='invalid')


class NLBSNFieldValidator(RegexValidator):
    """
    Validation for Dutch social security numbers (BSN).

    .. versionadded:: 1.6
    """

    error_message = _('Enter a valid BSN.')

    def __init__(self):
        super().__init__(regex=r'^\d{9}$', message=self.error_message)

    def bsn_checksum_ok(self, value):
        checksum = 0
        for i in range(9, 1, -1):
            checksum += int(value[9 - i]) * i
        checksum -= int(value[-1])

        return checksum % 11 == 0

    def __call__(self, value):
        super().__call__(value)

        if int(value) == 0:
            raise ValidationError(self.error_message, code='invalid')

        if not self.bsn_checksum_ok(value):
            raise ValidationError(self.error_message, code='invalid')


class NLLicensePlateFieldValidator(RegexValidator):
    """
    Validation for Dutch license plates.

    .. versionadded:: 2.1
    """

    error_message = _('Enter a valid license plate')

    VALIDATION_REGEXS = {
        "sidecode1": r"^[A-Z]{2}-[0-9]{2}-[0-9]{2}$",  # AA-99-99
        "sidecode2": r"^[0-9]{2}-[0-9]{2}-[A-Z]{2}$",  # 99-99-AA
        "sidecode3": r"^[0-9]{2}-[A-Z]{2}-[0-9]{2}$",  # 99-AA-99
        "sidecode4": r"^[A-Z]{2}-[0-9]{2}-[A-Z]{2}$",  # AA-99-AA
        "sidecode5": r"^[A-Z]{2}-[A-Z]{2}-[0-9]{2}$",  # AA-AA-99
        "sidecode6": r"^[0-9]{2}-[A-Z]{2}-[A-Z]{2}$",  # 99-AA-AA
        "sidecode7": r"^[0-9]{2}-[A-Z]{3}-[0-9]{1}$",  # 99-AAA-9
        "sidecode8": r"^[0-9]{1}-[A-Z]{3}-[0-9]{2}$",  # 9-AAA-99
        "sidecode9": r"^[A-Z]{2}-[0-9]{3}-[A-Z]{1}$",  # AA-999-A
        "sidecode10": r"^[A-Z]{1}-[0-9]{3}-[A-Z]{2}$",  # A-999-AA
        "sidecode11": r"^[A-Z]{3}-[0-9]{2}-[A-Z]{1}$",  # AAA-99-A
        "sidecode12": r"^[A-Z]{1}-[0-9]{2}-[A-Z]{3}$",  # A-99-AAA
        "sidecode13": r"^[0-9]{1}-[A-Z]{2}-[0-9]{3}$",  # 9-AA-999
        "sidecode14": r"^[0-9]{3}-[A-Z]{2}-[0-9]{1}$",  # 999-AA-9
        "sidecode_koninklijk_huis": r"^AA-[0-9]{2,3}(-[0-9]{2})?$",  # AA-99(-99)?
        "sidecode_internationaal_gerechtshof": r"^CDJ-[0-9]{3}$",  # CDJ-999
        "sidecode_bijzondere_toelating": r"^ZZ-[0-9]{2}-[0-9]{2}$",  # ZZ-99-99
        "sidecode_tijdelijk_voor_een_dag": r"^F-[0-9]{2}-[0-9]{2}$",  # F-99-99
        "sidecode_voertuig_binnen_of_buiten_nederland_brengen": r"^Z-[0-9]{2}-[0-9]{2}$",  # Z-99-99
    }

    def __init__(self):
        regex = r'(' + r'|'.join(self.VALIDATION_REGEXS.values()) + r')'
        super().__init__(regex=regex, message=self.error_message)
