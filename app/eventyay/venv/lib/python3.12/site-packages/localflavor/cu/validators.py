import datetime

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class CUIdentityCardNumberBirthdayValidator:
    """
    Validator for the Cuban identity card number birthday.

    Checks that the first 6 digits build a valid date.

    .. versionadded:: 1.6
    """
    message = _("Enter a valid date (yymmdd) for the first 6 digits of the Identity Card Number.")
    code = 'invalid_birthday'

    def __init__(self, message=None, code=None):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code

    def __call__(self, value):
        try:
            datetime.datetime.strptime(value[:6], '%y%m%d')
        except ValueError:
            raise ValidationError(self.message, code=self.code)
