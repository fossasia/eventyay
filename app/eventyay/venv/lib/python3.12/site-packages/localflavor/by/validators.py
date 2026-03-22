from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

PASS_NUMBER_VALIDATOR = RegexValidator(
    r'[A-Z]{2}\d{7}',
    message=_('Passport number format is: XX1234567')
)


PASS_ID_NUMBER_VALIDATOR = RegexValidator(
    r'\d{7}[A-Z]\d{3}[A-Z]{2}\d',
    message=_('ID format is: 1234567X123XX1')
)
