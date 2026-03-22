"""
    rest2html unittest
    ~~~~~~~~~~~~~~~~~~

    Unittests for rest2html, see: creole/rest2html/clean_writer.py

    :copyleft: 2011-2012 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import tempfile
import unittest

from creole.tests.utils.base_unittest import BaseCreoleTest


class ReSt2HtmlTests(BaseCreoleTest):
    def test_clean_link_table(self):
        self.assert_rest2html("""
            :homepage:
              http://code.google.com/p/python-creole/

            :sourcecode:
              http://github.com/jedie/python-creole
        """, """
            <table>
            <tr><th>homepage:</th><td><a href="http://code.google.com/p/python-creole/">http://code.google.com/p/python-creole/</a></td>
            </tr>
            <tr><th>sourcecode:</th><td><a href="http://github.com/jedie/python-creole">http://github.com/jedie/python-creole</a></td>
            </tr>
            </table>
        """)

    def test_clean_table(self):
        self.assert_rest2html("""
            +------------+------------+
            | Headline 1 | Headline 2 |
            +============+============+
            | cell one   | cell two   |
            +------------+------------+
        """, """
            <table>
            <colgroup>
            <col width="50%" />
            <col width="50%" />
            </colgroup>
            <tr><th>Headline 1</th>
            <th>Headline 2</th>
            </tr>
            <tr><td>cell one</td>
            <td>cell two</td>
            </tr>
            </table>
        """)

    def test_clean_list(self):
        self.assert_rest2html("""
            * item 1

                * item 1.1

                * item 1.2

            * item 2

            numbered list:

            #. item A

            #. item B
        """, """
            <ul>
            <li><p>item 1</p>
            <ul>
            <li>item 1.1</li>
            <li>item 1.2</li>
            </ul>
            </li>
            <li><p>item 2</p>
            </li>
            </ul>
            <p>numbered list:</p>
            <ol>
            <li>item A</li>
            <li>item B</li>
            </ol>
        """)

    def test_clean_headline(self):
        self.assert_rest2html("""
            ======
            head 1
            ======

            ------
            head 2
            ------
        """, """
            <h1>head 1</h1>
            <h2>head 2</h2>
        """)

    def test_include_disabled_by_default(self):
        self.assert_rest2html("""
            Include should be disabled by default.

            .. include:: doesntexist.txt
        """, """
            <p>Include should be disabled by default.</p>
        """, report_level=3)  # Set log level to "error" to suppress the waring output

    def test_include_enabled(self):
        test_content = "Content from include file."
        test_content = test_content.encode("utf-8")
        with tempfile.NamedTemporaryFile() as temp:
            temp.write(test_content)
            temp.flush()
            self.assert_rest2html(f"""
                Enable include and test it.

                .. include:: {temp.name}
            """, """
                <p>Enable include and test it.</p>
                <p>Content from include file.</p>
            """, file_insertion_enabled=True, input_encoding="utf-8")

    def test_raw_disabled_by_default(self):
        self.assert_rest2html("""
            Raw directive should be disabled by default.

            .. raw:: html

               <hr width=50 size=10>
        """, """
            <p>Raw directive should be disabled by default.</p>
        """, report_level=3)  # Set log level to "error" to suppress the waring output

    def test_raw_enabled(self):
        self.assert_rest2html("""
            Now RAW is enabled.

            .. raw:: html

               <hr width=50 size=10>
        """, """
            <p>Now RAW is enabled.</p>
            <hr width=50 size=10>
        """, raw_enabled=True)

    def test_preserve_image_alignment(self):
        self.assert_rest2html("""
            Image alignment should be preserved.

            .. image:: foo.png
               :align: right
        """, """
            <p>Image alignment should be preserved.</p>
            <img alt="foo.png" src="foo.png" align="right" />
        """)

    def test_preserve_figure_alignment(self):
        self.assert_rest2html("""
            Image alignment should be preserved.

            .. figure:: bar.png
               :align: right
        """, """
            <p>Image alignment should be preserved.</p>
            <img alt="bar.png" src="bar.png" align="right" />
        """)


if __name__ == '__main__':
    unittest.main()
