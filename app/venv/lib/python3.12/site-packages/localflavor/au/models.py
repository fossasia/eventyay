from django.db.models import CharField
from django.utils.translation import gettext_lazy as _

from . import forms
from .au_states import STATE_CHOICES
from .validators import AUBusinessNumberFieldValidator, AUCompanyNumberFieldValidator, AUTaxFileNumberFieldValidator


class AUStateField(CharField):
    """
    A model field that stores the three-letter Australian state abbreviation in the database.

    It is represented with :data:`~localflavor.au.au_states.STATE_CHOICES`` choices.
    """

    description = _("Australian State")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = STATE_CHOICES
        kwargs['max_length'] = 3
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class AUPostCodeField(CharField):
    """
    A model field that stores the four-digit Australian postcode in the database.

    This field is represented by forms as a :class:`~localflavor.au.forms.AUPostCodeField` field.
    """

    description = _("Australian Postcode")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 4
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.AUPostCodeField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class AUBusinessNumberField(CharField):
    """
    A model field that checks that the value is a valid Australian Business Number (ABN).

    .. versionadded:: 1.3
    """

    description = _("Australian Business Number")

    validators = [AUBusinessNumberFieldValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 11
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.AUBusinessNumberField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def to_python(self, value):
        """Ensure the ABN is stored without spaces."""
        value = super().to_python(value)

        if value is not None:
            return ''.join(value.split())

        return value


class AUCompanyNumberField(CharField):
    """
    A model field that checks that the value is a valid Australian Company Number (ACN).

    .. versionadded:: 1.5
    """

    description = _("Australian Company Number")

    validators = [AUCompanyNumberFieldValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 9
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.AUCompanyNumberField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def to_python(self, value):
        """Ensure the ACN is stored without spaces."""
        value = super().to_python(value)

        if value is not None:
            return ''.join(value.split())

        return value


class AUTaxFileNumberField(CharField):
    """
    A model field that checks that the value is a valid Tax File Number (TFN).

    A TFN is a number issued to a person by the Commissioner of Taxation and
    is used to verify client identity and establish their income levels.
    It is a eight or nine digit number without any embedded meaning.

    .. versionadded:: 1.4
    """

    description = _("Australian Tax File Number")

    validators = [AUTaxFileNumberFieldValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 11
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.AUTaxFileNumberField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def to_python(self, value):
        """Ensure the TFN is stored without spaces."""
        value = super().to_python(value)

        if value is not None:
            return ''.join(value.split())

        return value
