from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


class INPANCardNumberValidator(RegexValidator):
    """
    A validator for Indian Permanent Account Number(PAN) Card field.
    """

    default_error_messages = {
        'invalid': _('Please enter a valid Indian PAN card number.'),
    }

    def __init__(self,*args, **kwargs):
        # documentation for validation rules are available in ``forms.INPANCardNumberFormField``
        super().__init__(regex = r'^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$', *args,**kwargs)