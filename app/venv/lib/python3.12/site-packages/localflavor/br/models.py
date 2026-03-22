from django.db.models.fields import CharField
from django.utils.translation import gettext_lazy as _

from . import validators
from .br_states import STATE_CHOICES
from . import forms


class BRStateField(CharField):
    """
    A model field for states of Brazil.

    Forms represent it as a :class:`~localflavor.br.forms.BRStateSelect` field.
    
    """

    description = _("State of Brazil (two uppercase letters)")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = STATE_CHOICES
        kwargs['max_length'] = 2
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class BRCPFField(CharField):
    """
    A model field for the brazilian document named of CPF (Cadastro de Pessoa Física)

    Forms represent it as a :class:`~localflavor.br.forms.BRCPFField` field.

    .. versionadded:: 2.2
    """

    description = _("CPF Document")

    default_error_messages = {
        'invalid': _("Invalid CPF number."),
        'max_digits': _("This field requires at most 11 digits or 14 characters."),
    }

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 14
        super().__init__(*args, **kwargs)
        self.validators.append(validators.BRCPFValidator())
    
    def formfield(self, **kwargs):
        defaults = {'form_class': forms.BRCPFField}
        defaults.update(kwargs)
        return super().formfield(**defaults)



class BRCNPJField(CharField):
    """
    A model field for the brazilian document named of CNPJ (Cadastro Nacional de Pessoa Jurídica)

    Forms represent it as a :class:`~localflavor.br.forms.BRCNPJField` field.

    .. versionadded:: 2.2
    """

    description = _("CNPJ Document")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 18
        super().__init__(*args, **kwargs)
        self.validators.append(validators.BRCNPJValidator())

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.BRCNPJField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

class BRPostalCodeField(CharField):
    """
    A model field for the brazilian zip code

    Forms represent it as a :class:`~localflavor.br.forms.BRZipCOdeField` field.

    .. versionadded:: 2.2
    """

    description = _("Postal Code")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 9
        super().__init__(*args, **kwargs)
        self.validators.append(validators.BRPostalCodeValidator())

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.BRZipCodeField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
