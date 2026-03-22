import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

postal_code_re = re.compile(r'^\d{5}-\d{3}$')
cnpj_digits_re = re.compile(r'^(\d{2})[.-]?(\d{3})[.-]?(\d{3})/(\d{4})-(\d{2})$')
cpf_digits_re = re.compile(r'^(\d{3})\.(\d{3})\.(\d{3})-(\d{2})$')


def dv_maker(v):
    if v >= 2:
        return 11 - v
    return 0


class BRPostalCodeValidator(RegexValidator):
    """
    A validator for Brazilian Postal Codes (CEP).

    .. versionadded:: 2.2
    """

    def __init__(self, *args, **kwargs):
        self.message = _('Enter a postal code in the format 00000-000.')
        super().__init__(postal_code_re, *args, **kwargs)


class BRCNPJValidator(RegexValidator):
    """
    Validator for brazilian CNPJ.

    .. versionadded:: 2.2
    """

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            regex=cnpj_digits_re,
            message=_("Invalid CNPJ number."),
            **kwargs
        )

    def __call__(self, value):
        orig_dv = value[-2:]

        if not value.isdigit():
            cnpj = cnpj_digits_re.search(value)
            if cnpj:
                value = ''.join(cnpj.groups())
            else:
                raise ValidationError(self.message, code='invalid')

        if len(value) != 14:
            raise ValidationError(self.message, code='max_digits')

        new_1dv = sum([i * int(value[idx]) for idx, i in enumerate(list(range(5, 1, -1)) + list(range(9, 1, -1)))])
        new_1dv = dv_maker(new_1dv % 11)
        value = value[:-2] + str(new_1dv) + value[-1]
        new_2dv = sum([i * int(value[idx]) for idx, i in enumerate(list(range(6, 1, -1)) + list(range(9, 1, -1)))])
        new_2dv = dv_maker(new_2dv % 11)
        value = value[:-1] + str(new_2dv)
        if value[-2:] != orig_dv:
            raise ValidationError(self.message, code='invalid')


class BRCPFValidator(RegexValidator):
    """
    Validator for brazilian CPF.

    .. versionadded:: 2.2
    """

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            regex=cpf_digits_re,
            message=_("Invalid CPF number."),
            **kwargs
        )

    def __call__(self, value):
        if not value.isdigit():
            cpf = cpf_digits_re.search(value)
            if cpf:
                value = ''.join(cpf.groups())
            else:
                raise ValidationError(self.message, code='invalid')

        if len(value) != 11:
            raise ValidationError(self.message, code='max_digits')

        orig_dv = value[-2:]
        new_1dv = sum([i * int(value[idx])
                       for idx, i in enumerate(range(10, 1, -1))])
        new_1dv = dv_maker(new_1dv % 11)
        value = value[:-2] + str(new_1dv) + value[-1]
        new_2dv = sum([i * int(value[idx])
                       for idx, i in enumerate(range(11, 1, -1))])
        new_2dv = dv_maker(new_2dv % 11)
        value = value[:-1] + str(new_2dv)
        if value[-2:] != orig_dv:
            raise ValidationError(self.message, code='invalid')
        if value.count(value[0]) == 11:
            raise ValidationError(self.message, code='invalid')
