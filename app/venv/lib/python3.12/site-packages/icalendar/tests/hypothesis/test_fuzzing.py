import string
import unittest

import hypothesis.strategies as st
from hypothesis import given, settings

from icalendar.parser import Contentline, Contentlines, Parameters


def printable_characters(**kw):
    return st.text(st.characters(blacklist_categories=("Cc", "Cs"), **kw))


key = st.text(string.ascii_letters + string.digits, min_size=1)
value = printable_characters(blacklist_characters='\\;:"')


class TestFuzzing(unittest.TestCase):
    @given(
        lines=st.lists(st.tuples(key, st.dictionaries(key, value), value), min_size=1)
    )
    @settings(max_examples=10**3)
    def test_main(self, lines):
        cl = Contentlines()
        for key, params, value in lines:
            try:
                params = Parameters(**params)  # noqa: PLW2901
            except TypeError:
                # Happens when there is a random parameter 'self'...
                continue
            cl.append(Contentline.from_parts(key, params, value))
        cl.append("")

        assert Contentlines.from_ical(cl.to_ical()) == cl
