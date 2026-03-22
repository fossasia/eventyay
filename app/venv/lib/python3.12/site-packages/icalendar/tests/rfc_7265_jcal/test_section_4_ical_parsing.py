"""Converting from jCal into iCalendar - :rfc:`7265`

- parameters
- properties
- components

"""

import pytest

from icalendar.parser import Parameters


@pytest.mark.parametrize("jcal", [{}, {"value": "DATE-TIME"}, {"x-slack": "30.3"}])
def test_parameters_from_jcal(jcal):
    """General constrints for parameter parsing.

    > When converting [...] property parameter names,
    > the names SHOULD be converted to uppercase.
    """
    params = Parameters.from_jcal(jcal)
    assert len(params) == len(jcal)
    assert all(key.isupper() for key in params)
