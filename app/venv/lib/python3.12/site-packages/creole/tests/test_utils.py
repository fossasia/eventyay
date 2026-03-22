"""
    unittest for some utils
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2011 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import unittest

from creole.shared.markup_table import MarkupTable
from creole.tests.utils.utils import MarkupTest


class UtilsTests(MarkupTest):

    def test_assertEqual(self):
        self.assertRaises(
            AssertionError, self.assertEqual, "foo", "bar"
        )

    def test_prepare_text_base(self):
        out1 = self._prepare_text("""
            one line
            line two""")
        self.assertEqual(out1, "one line\nline two")

        out2 = self._prepare_text("""
            one line
            line two
        """)
        self.assertEqual(out2, "one line\nline two")

    def test_prepare_text_last_line_empty(self):

        out3 = self._prepare_text("""
            one line
            line two

        """)
        self.assertEqual(out3, "one line\nline two\n")

    def test_prepare_text_empty_line(self):
        self.assertEqual(self._prepare_text("""
            line one

            line two
        """), "line one\n\nline two")

    def test_prepare_text_first_line_empty(self):
        self.assertEqual(self._prepare_text("""

            line one
            line two
        """), "\nline one\nline two")

    def test_prepare_space_and_line_end(self):
        self.assertEqual(self._prepare_text("\n  111  \n  222"), "111\n222")

    def test_prepare_text_indent_line(self):
        self.assertEqual("line one\n  indent line\nline two", self._prepare_text("""
            line one
              indent line
            line two
        """))

    def test_prepare_text_indent_with_empty_end(self):
        out4 = self._prepare_text("""
            one line
                line two

        """)
        self.assertEqual(out4, "one line\n    line two\n")

    def assertEqual2(self, first, second, msg=""):
        self.assertNotEqual(first, second, msg)

#        first = self._prepare_text(first)
        second = self._prepare_text(second)

        self.assertEqual(first, second, msg)

    def test_markup_table_creole(self):
        t = MarkupTable(head_prefix="* ")
        t.add_tr()
        t.add_th("head1")
        t.add_th("head2")
        t.add_tr()
        t.add_td("1.1.")
        t.add_td("1.2.")
        t.add_tr()
        t.add_td("2.1.")
        t.add_td("2.2.")
        table = t.get_table_markup()

        self.assertEqual2(
            table,
            """
            |* head1 |* head2 |
            | 1.1.   | 1.2.   |
            | 2.1.   | 2.2.   |
            """
        )

    def test_markup_table_textile(self):
        t = MarkupTable(head_prefix="_. ", auto_width=False)
        t.add_tr()
        t.add_th("head1")
        t.add_th("head2")
        t.add_tr()
        t.add_td("1.1.")
        t.add_td("1.2.")
        t.add_tr()
        t.add_td("2.1.")
        t.add_td("2.2.")
        table = t.get_table_markup()

        self.assertEqual2(
            table,
            """
            |_. head1|_. head2|
            |1.1.|1.2.|
            |2.1.|2.2.|
            """
        )

    def test_markup_table_rest(self):
        t = MarkupTable(head_prefix="")
        t.add_tr()
        t.add_th("head1")
        t.add_th("head2")
        t.add_tr()
        t.add_td("1.1.")
        t.add_td("1.2.")
        t.add_tr()
        t.add_td("2.1.")
        t.add_td("2.2.")
        table = t.get_rest_table()

        self.assertEqual2(
            table,
            """
            +-------+-------+
            | head1 | head2 |
            +=======+=======+
            | 1.1.  | 1.2.  |
            +-------+-------+
            | 2.1.  | 2.2.  |
            +-------+-------+
            """
        )


if __name__ == '__main__':
    unittest.main()
