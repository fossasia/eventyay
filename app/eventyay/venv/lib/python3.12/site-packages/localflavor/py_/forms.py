"""PY-specific Form helpers."""

from django.forms.fields import Select

from .py_department import DEPARTMENT_CHOICES, DEPARTMENT_ROMAN_CHOICES


class PyDepartmentSelect(Select):
    """A Select widget with a list of Paraguayan departments as choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=DEPARTMENT_CHOICES)


class PyNumberedDepartmentSelect(Select):
    """A Select widget with a roman numbered list of Paraguayan departments as choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=DEPARTMENT_ROMAN_CHOICES)
