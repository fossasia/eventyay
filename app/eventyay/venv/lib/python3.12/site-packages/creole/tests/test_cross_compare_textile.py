"""
    cross compare textile unittest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Compare all similarities between:
        * textile2html (used the python textile module)
        * html2textile

    Note: This only works fine if there is no problematic whitespace handling.
        In this case, we must test in test_creole2html.py or test_html2creole.py

    :copyleft: 2008-2014 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import unittest

from creole.tests.utils.base_unittest import BaseCreoleTest


class CrossCompareTextileTests(BaseCreoleTest):
    def test_typeface_basic(self):
        self.cross_compare_textile(
            textile_string="""
                _emphasis_
                *strong*
                __italic__
                **bold**
                ??citation??
                -deleted text-
                +inserted text+
                ^superscript^
                ~subscript~
                %span%
                @code@
            """,
            html_string="""
                <p><em>emphasis</em><br />

                <strong>strong</strong><br />

                <i>italic</i><br />

                <b>bold</b><br />

                <cite>citation</cite><br />

                <del>deleted text</del><br />

                <ins>inserted text</ins><br />

                <sup>superscript</sup><br />

                <sub>subscript</sub><br />

                <span>span</span><br />

                <code>code</code></p>
            """
        )

    def test_escape_in_pre(self):
        self.cross_compare_textile(
            textile_string="""
                <pre>
                <html escaped>
                </pre>
            """,
            html_string="""
                <pre>
                &lt;html escaped&gt;
                </pre>
            """)


if __name__ == '__main__':
    unittest.main()
