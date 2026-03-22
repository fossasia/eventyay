from django.conf import settings
from django.forms.widgets import MultiWidget, TextInput
from phonenumbers import (
    national_significant_number,
    region_code_for_number,
    region_codes_for_country_code,
)

from phonenumber_field.phonenumber import PhoneNumber, to_python


class PhoneNumberPrefixWidget(MultiWidget):
    """
    Companion widget of :class:`~phonenumber_field.formfields.SplitPhoneNumberField`.
    """

    def decompress(self, value):
        if isinstance(value, PhoneNumber):
            region_code = region_code_for_number(value)
            national_number = national_significant_number(value)
            return [region_code, national_number]
        return [None, None]


class RegionalPhoneNumberWidget(TextInput):
    """
    A :class:`~django.forms.Widget` that prefers displaying numbers in the
    national format, and falls back to :setting:`PHONENUMBER_DEFAULT_FORMAT`
    for international numbers.
    """

    input_type = "tel"

    def __init__(self, region=None, attrs=None):
        """
        :keyword str region: 2-letter country code as defined in ISO 3166-1.
            When not supplied, defaults to :setting:`PHONENUMBER_DEFAULT_REGION`
        :keyword dict attrs: See :attr:`django.forms.Widget.attrs`
        """
        if region is None:
            region = getattr(settings, "PHONENUMBER_DEFAULT_REGION", None)
        self.region = region
        super().__init__(attrs)

    def format_value(self, value):
        number = value
        if not isinstance(number, PhoneNumber):
            try:
                number = to_python(value, region=self.region)
            except TypeError:
                pass
        if isinstance(number, PhoneNumber) and number.country_code:
            region_codes = region_codes_for_country_code(number.country_code)
            if self.region in region_codes:
                return number.as_national
        return super().format_value(value)
