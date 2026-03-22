from django.db.models import CharField
from django.utils.translation import gettext_lazy as _

from .forms import MXCLABEField as MXCLABEFormField
from .forms import MXCURPField as MXCURPFormField
from .forms import MXRFCField as MXRFCFormField
from .forms import MXSocialSecurityNumberField as MXSocialSecurityNumberFormField
from .forms import MXZipCodeField as MXZipCodeFormField
from .mx_states import STATE_CHOICES


class MXStateField(CharField):
    """A model field that stores the three or four letter Mexican state abbreviation in the database."""

    description = _("Mexico state (three or four uppercase letters)")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = STATE_CHOICES
        kwargs['max_length'] = 4
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class MXZipCodeField(CharField):
    """A model field that forms represent as a forms.MXZipCodeField field and stores the five-digit Mexican zip code."""

    description = _("Mexico zip code")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 5
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': MXZipCodeFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class MXRFCField(CharField):
    """A model field that forms represent as a forms.MXRFCField field and stores the value of a valid Mexican RFC."""

    description = _("Mexican RFC")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 13
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': MXRFCFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class MXCLABEField(CharField):
    """
    A model field that forms represent as a forms.MXCURPField field and stores the value of a valid Mexican CLABE.

    .. versionadded:: 1.4
    """

    description = _("Mexican CLABE")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 18
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': MXCLABEFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class MXCURPField(CharField):
    """A model field that forms represent as a forms.MXCURPField field and stores the value of a valid Mexican CURP."""

    description = _("Mexican CURP")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 18
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': MXCURPFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class MXSocialSecurityNumberField(CharField):
    """
    A model field that forms represent as a forms.MXSocialSecurityNumberField field.

    It stores the value of a valid Mexican Social Security Number.
    """

    description = _("Mexican Social Security Number")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 11
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': MXSocialSecurityNumberFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
