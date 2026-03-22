import phonenumbers
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from phonenumber_field.phonenumber import PhoneNumber, to_python


def validate_international_phonenumber(value):
    phone_number = to_python(value)
    if isinstance(phone_number, PhoneNumber) and not phone_number.is_valid():
        raise ValidationError(
            _("The phone number entered is not valid."), code="invalid"
        )


def validate_phonenumber(value):
    phone_number = to_python(value)
    if isinstance(phone_number, PhoneNumber) and not (
        phonenumbers.is_valid_number(phone_number)
        or phonenumbers.is_valid_short_number(phone_number)
    ):
        raise ValidationError(
            _("The phone number entered is not valid."), code="invalid"
        )
