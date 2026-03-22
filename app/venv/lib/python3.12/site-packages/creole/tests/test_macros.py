"""
    Creole unittest macros
    ~~~~~~~~~~~~~~~~~~~~~~

    Note: all mecro functions must return unicode!

    :copyleft: 2008-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import json


def unittest_macro1(**kwargs):
    """
    >>> unittest_macro1(foo="bar")
    '[test macro1 - kwargs: foo="bar"]'

    >>> unittest_macro1()
    '[test macro1 - kwargs: ]'

    >>> unittest_macro1(a=1,b=2)
    '[test macro1 - kwargs: a=1,b=2]'
    """
    kwargs = ','.join(f'{k}={json.dumps(v)}' for k, v in sorted(kwargs.items()))
    return f"[test macro1 - kwargs: {kwargs}]"


def unittest_macro2(char, text):
    """
    >>> unittest_macro2(char="|", text="a\\nb")
    'a|b'
    """
    return char.join(text.split())
