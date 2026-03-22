from django.db import models

from .validators import EGNValidator, EIKValidator


class BGEGNField(models.CharField):
    """
    Field that stores Bulgarian unique citizenship number (EGN).

    This is shortcut for::

        models.CharField(max_length=10, validators=[localflavor.bg.validators.egn_validator])
    """

    default_validators = models.CharField.default_validators + [EGNValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 10
        super().__init__(*args, **kwargs)


class BGEIKField(models.CharField):
    """
    Field that stores Bulgarian EIK/BULSTAT codes.

    This is shortcut for::

        models.CharField(max_length=13, validators=[localflavor.bg.validators.eik_validator])
    """

    default_validators = models.CharField.default_validators + [EIKValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 13
        super().__init__(*args, **kwargs)
