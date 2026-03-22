"""Tests for issue #987: property class modularization.

Verifies that mutable property types (vDDDLists, vRecur) are not hashable.
"""

from datetime import timedelta

import pytest

from icalendar import vDDDLists, vRecur


def test_vdddtypes_cannot_be_hashed():
    """Mutable objects are not hashable."""
    with pytest.raises(TypeError):
        hash(vDDDLists([]))

    with pytest.raises(TypeError):
        hash(vDDDLists([timedelta(0)]))


def test_vrecur_cannot_be_hashed():
    """Mutable objects are not hashable."""
    with pytest.raises(TypeError):
        hash(vRecur([]))
