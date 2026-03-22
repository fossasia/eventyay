"""NL-specific Form helpers."""

import re

from django import forms

from .nl_provinces import PROVINCE_CHOICES
from .validators import NLBSNFieldValidator, NLLicensePlateFieldValidator, NLZipCodeFieldValidator


class NLZipCodeField(forms.CharField):
    """A Dutch zip code field."""

    default_validators = [NLZipCodeFieldValidator()]

    def clean(self, value):
        if isinstance(value, str):
            value = value.upper().replace(' ', '')

            if len(value) == 6:
                value = '%s %s' % (value[:4], value[4:])

        return super().clean(value)


class NLProvinceSelect(forms.Select):
    """A Select widget that uses a list of provinces of the Netherlands as it's choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=PROVINCE_CHOICES)


class NLBSNFormField(forms.CharField):
    """
    A Dutch social security number (BSN) field.

    https://nl.wikipedia.org/wiki/Burgerservicenummer

    Note that you may only process the BSN if you have a legal basis to do so!

    .. versionadded:: 1.6
    """

    default_validators = [NLBSNFieldValidator()]

    def __init__(self, **kwargs):
        kwargs['max_length'] = 9
        super().__init__(**kwargs)


class NLLicensePlateFormField(forms.CharField):
    """
    A Dutch license plate field.

    https://www.rdw.nl/
    https://nl.wikipedia.org/wiki/Nederlands_kenteken

    .. versionadded:: 2.1
    """

    default_validators = [NLLicensePlateFieldValidator()]

    SANITIZE_REGEXS = {
        "sidecode1": re.compile(r"^([A-Z]{2})([0-9]{2})([0-9]{2})$"),  # AA-99-99
        "sidecode2": re.compile(r"^([0-9]{2})([0-9]{2})([A-Z]{2})$"),  # 99-99-AA
        "sidecode3": re.compile(r"^([0-9]{2})([A-Z]{2})([0-9]{2})$"),  # 99-AA-99
        "sidecode4": re.compile(r"^([A-Z]{2})([0-9]{2})([A-Z]{2})$"),  # AA-99-AA
        "sidecode5": re.compile(r"^([A-Z]{2})([A-Z]{2})([0-9]{2})$"),  # AA-AA-99
        "sidecode6": re.compile(r"^([0-9]{2})([A-Z]{2})([A-Z]{2})$"),  # 99-AA-AA
        "sidecode7": re.compile(r"^([0-9]{2})([A-Z]{3})([0-9]{1})$"),  # 99-AAA-9
        "sidecode8": re.compile(r"^([0-9]{1})([A-Z]{3})([0-9]{2})$"),  # 9-AAA-99
        "sidecode9": re.compile(r"^([A-Z]{2})([0-9]{3})([A-Z]{1})$"),  # AA-999-A
        "sidecode10": re.compile(r"^([A-Z]{1})([0-9]{3})([A-Z]{2})$"),  # A-999-AA
        "sidecode11": re.compile(r"^([A-Z]{3})([0-9]{2})([A-Z]{1})$"),  # AAA-99-A
        "sidecode12": re.compile(r"^([A-Z]{1})([0-9]{2})([A-Z]{3})$"),  # A-99-AAA
        "sidecode13": re.compile(r"^([0-9]{1})([A-Z]{2})([0-9]{3})$"),  # 9-AA-999
        "sidecode14": re.compile(r"^([0-9]{3})([A-Z]{2})([0-9]{1})$"),  # 999-AA-9
        "sidecode_koninklijk_huis": re.compile(r"^(AA)([0-9]{2,3})(([0-9]{2})?)$"),  # AA-99(-99)?
        "sidecode_internationaal_gerechtshof": re.compile(r"^(CDJ)([0-9]{3})$"),  # CDJ-999
        "sidecode_bijzondere_toelating": re.compile(r"^(ZZ)([0-9]{2})([0-9]{2})$"),  # ZZ-99-99
        "sidecode_tijdelijk_voor_een_dag": re.compile(r"^(F)([0-9]{2})([0-9]{2})$"),  # F-99-99
        "sidecode_voertuig_binnen_of_buiten_nederland_brengen": re.compile(r"^(Z)([0-9]{2})([0-9]{2})$"),  # Z-99-99
    }

    def __init__(self, **kwargs):
        kwargs['max_length'] = 8
        super().__init__(**kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value:
            value = value.upper().replace('-', '')
            for sidecode, regex in self.SANITIZE_REGEXS.items():
                match = regex.match(value)
                if match:
                    return '-'.join(match.groups())
        return value
