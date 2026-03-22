import phonenumbers
from django.conf import settings
from django.core import validators
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms.fields import CharField, ChoiceField, MultiValueField
from django.utils import translation
from django.utils.text import format_lazy
from django.utils.translation import pgettext, pgettext_lazy
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE, COUNTRY_CODES_FOR_NON_GEO_REGIONS

from phonenumber_field import widgets
from phonenumber_field.phonenumber import to_python, validate_region
from phonenumber_field.validators import validate_international_phonenumber

try:
    import babel
except ModuleNotFoundError:
    babel = None  # type: ignore

GEO_COUNTRY_CODE_TO_REGION_CODE = COUNTRY_CODE_TO_REGION_CODE.copy()
for country_code in COUNTRY_CODES_FOR_NON_GEO_REGIONS:
    del GEO_COUNTRY_CODE_TO_REGION_CODE[country_code]
# ISO 3166-1 alpha-2 to national prefix
REGION_CODE_TO_COUNTRY_CODE = {
    region_code: country_code
    for country_code, region_codes in GEO_COUNTRY_CODE_TO_REGION_CODE.items()
    for region_code in region_codes
}


class PhoneNumberField(CharField):
    default_validators = [validate_international_phonenumber]
    widget = widgets.RegionalPhoneNumberWidget

    def __init__(self, *args, region=None, widget=None, **kwargs):
        """
        :keyword str region: 2-letter country code as defined in ISO 3166-1.
            When not supplied, defaults to :setting:`PHONENUMBER_DEFAULT_REGION`
        :keyword django.forms.Widget widget: defaults to
            :class:`~phonenumber_field.widgets.RegionalPhoneNumberWidget`
        """
        validate_region(region)
        self.region = region or getattr(settings, "PHONENUMBER_DEFAULT_REGION", None)

        if widget is None:
            try:
                widget = self.widget(region=self.region)
            except TypeError:
                widget = self.widget()

        super().__init__(*args, widget=widget, **kwargs)
        self.widget.input_type = "tel"

        if "invalid" not in self.error_messages:
            if self.region:
                number = phonenumbers.example_number(self.region)
                example_number = to_python(number).as_national
                error_message = pgettext_lazy(
                    "{example_number} is a national phone number.",
                    "Enter a valid phone number (e.g. {example_number}) "
                    "or a number with an international call prefix.",
                )
            else:
                example_number = "+12125552368"  # Ghostbusters
                error_message = pgettext_lazy(
                    "{example_number} is an international phone number.",
                    "Enter a valid phone number (e.g. {example_number}).",
                )
            self.error_messages["invalid"] = format_lazy(
                error_message, example_number=example_number
            )

    def to_python(self, value):
        if value in validators.EMPTY_VALUES:
            return self.empty_value
        return to_python(value, region=self.region)


def localized_choices(language):
    if babel is None:
        raise ImproperlyConfigured(
            "The PhonePrefixSelect widget requires the babel package be installed."
        )
    choices = [("", "---------")]
    locale_name = translation.to_locale(language)
    locale = babel.Locale(locale_name)
    for region_code, country_code in REGION_CODE_TO_COUNTRY_CODE.items():
        region_name = locale.territories.get(region_code)
        if region_name:
            choices.append((region_code, f"{region_name} +{country_code}"))
    return choices


class PrefixChoiceField(ChoiceField):
    def __init__(self, *, choices=None, **kwargs):
        if choices is None:
            language = translation.get_language() or settings.LANGUAGE_CODE
            choices = localized_choices(language)
            choices.sort(key=lambda item: item[1])
        super().__init__(choices=choices, **kwargs)


class SplitPhoneNumberField(MultiValueField):
    default_validators = [validate_international_phonenumber]
    widget = widgets.PhoneNumberPrefixWidget

    def __init__(
        self,
        *,
        initial=None,
        region=None,
        widget=None,
        empty_value="",
        max_length=None,
        **kwargs,
    ):
        """
        :keyword list initial: A two-elements iterable:

            #. the region code, an :class:`str`, the 2-letter country code
               as defined in ISO 3166-1.

            #. the phone number, an :class:`str`

            When ``initial`` is not provided, the ``region`` keyword argument
            is used as the initial for the region field if specified, otherwise
            :setting:`PHONENUMBER_DEFAULT_REGION` is used.

            See :attr:`django.forms.Field.initial`.
        :keyword str region: 2-letter country code as defined in ISO 3166-1.
            When not supplied, defaults to :setting:`PHONENUMBER_DEFAULT_REGION`
        :keyword ~django.forms.MultiWidget widget: defaults to
            :class:`~phonenumber_field.widgets.PhoneNumberPrefixWidget`
        :keyword empty_value: value to use when the field is empty
        :keyword int max_length: maximum length of the phone number, when
            represented as :setting:`PHONENUMBER_DB_FORMAT`.
        """
        validate_region(region)
        region = region or getattr(settings, "PHONENUMBER_DEFAULT_REGION", None)
        if initial is None and region:
            initial = [region, None]
        prefix_field = self.prefix_field()
        number_field = self.number_field()
        fields = (prefix_field, number_field)
        if widget is None:
            widget = self.widget((prefix_field.widget, number_field.widget))
        self.empty_value = empty_value
        self.max_length = max_length
        super().__init__(fields, initial=initial, widget=widget, **kwargs)

    def prefix_field(self):
        """
        Returns the default :class:`~django.forms.Field` for the phone
        number prefix field.

        Use this hook to set widget attributes or update the field definition.
        """
        return PrefixChoiceField()

    def number_field(self):
        """
        Returns the default :class:`~django.forms.Field` for the phone
        number field.

        Use this hook to set widget attributes or update the field definition.
        """
        number_field = CharField()
        number_field.widget.input_type = "tel"
        return number_field

    def invalid_error_message(self):
        """
        Hook to customize ``error_messages["invalid"]`` for a given region.

        Include the example number in the message with the ``{example_number}``
        placeholder.
        """
        return pgettext(
            "{example_number} is a national phone number.",
            "Enter a valid phone number (e.g. {example_number}).",
        )

    def compress(self, data_list):
        if not data_list:
            return self.empty_value
        region, national_number = data_list
        return to_python(national_number, region=region)

    def clean(self, value):
        if not self.disabled:
            prefix_field = self.fields[0]
            try:
                region = prefix_field.clean(value[0])
            except ValidationError:
                pass  # The parent class handles validation.
            else:
                if region:
                    number = phonenumbers.example_number(region)
                    example_number = to_python(number).as_national
                    error_message = self.invalid_error_message()
                    self.error_messages["invalid"] = format_lazy(
                        error_message,
                        example_number=example_number,
                    )
        clean_value = super().clean(value)
        if clean_value not in self.empty_values and self.max_length is not None:
            phonenumber_str = clean_value.format_as(
                getattr(settings, "PHONENUMBER_DB_FORMAT", "E164")
            )
            if len(phonenumber_str) > self.max_length:
                raise ValidationError(
                    format_lazy(
                        "Ensure this value has no more than {max_length} characters, "
                        "“{value}” is {length} characters long.",
                        max_length=self.max_length,
                        value=phonenumber_str,
                        length=len(phonenumber_str),
                    )
                )
        return clean_value
