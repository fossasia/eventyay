"""
    cross compare reStructuredText unittest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Compare all similarities between:
        * rest2html (used docutils)
        * html2rest

    :copyleft: 2011-2012 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import unittest

from creole.tests.utils.base_unittest import BaseCreoleTest


class CrossCompareReStTests(BaseCreoleTest):
    def test_entities(self):
        self.cross_compare_rest(
            rest_string="""
                less-than sign: <

                greater-than sign: >
            """,
            html_string="""
                <p>less-than sign: &lt;</p>
                <p>greater-than sign: &gt;</p>
            """,
            # debug=True
        )

    def test_bullet_lists_basic(self):
        self.cross_compare_rest(
            rest_string="""
                * item 1

                * item 2

                * item 3
            """,
            html_string="""
                <ul>
                <li>item 1</li>
                <li>item 2</li>
                <li>item 3</li>
                </ul>
            """,
            # debug=True
        )

    def test_numbered_lists(self):
        self.cross_compare_rest(
            rest_string="""
            #. item 1

            #. item 2

                #. item 2.1

                #. a `link in </url/>`_ list item 2.2

            #. item 3
            """,
            html_string="""
            <ol>
            <li><p>item 1</p>
            </li>
            <li><p>item 2</p>
            <ol>
            <li>item 2.1</li>
            <li>a <a href="/url/">link in</a> list item 2.2</li>
            </ol>
            </li>
            <li><p>item 3</p>
            </li>
            </ol>
            """,
            # debug=True
        )

    def test_bullet_lists_nested(self):
        self.cross_compare_rest(
            rest_string="""
                A nested bullet lists:

                * item 1

                    * A **bold subitem 1.1** here.

                        * subsubitem 1.1.1

                        * subsubitem 1.1.2 with inline |substitution text| image.

                    * subitem 1.2

                * item 2

                    * subitem 2.1

                    * *bold 2.2*

                .. |substitution text| image:: /url/to/image.png

                Text under list.
            """,
            html_string="""
                <p>A nested bullet lists:</p>
                <ul>
                <li><p>item 1</p>
                <ul>
                <li><p>A <strong>bold subitem 1.1</strong> here.</p>
                <ul>
                <li>subsubitem 1.1.1</li>
                <li>subsubitem 1.1.2 with inline <img alt="substitution text" src="/url/to/image.png" /> image.</li>
                </ul>
                </li>
                <li><p>subitem 1.2</p>
                </li>
                </ul>
                </li>
                <li><p>item 2</p>
                <ul>
                <li>subitem 2.1</li>
                <li><em>bold 2.2</em></li>
                </ul>
                </li>
                </ul>
                <p>Text under list.</p>
            """,
            # debug=True
        )

    def test_typeface_basic(self):
        """
        http://docutils.sourceforge.net/docs/user/rst/quickref.html#inline-markup
        """
        self.cross_compare_rest(
            rest_string="""
                *emphasis* **strong**
            """,
            html_string="""
                <p><em>emphasis</em> <strong>strong</strong></p>
            """
        )

    def test_substitution_image_with_alt(self):
        self.cross_compare_rest(
            rest_string="""
                A inline |substitution text| image.

                .. |substitution text| image:: /url/to/image.png

                ...and some text below.
            """,
            html_string="""
                <p>A inline <img alt="substitution text" src="/url/to/image.png" /> image.</p>
                <p>...and some text below.</p>
            """
        )

    def test_table(self):
        self.cross_compare(
            rest_string="""
                before table.

                +------------+
                | table item |
                +------------+

                After table.
            """,
            html_string="""
                <p>before table.</p>
                <table>
                <colgroup>
                <col width="100%" />
                </colgroup>
                <tr><td>table item</td>
                </tr>
                </table>
                <p>After table.</p>
            """
        )

    def test_link_in_table1(self):
        self.cross_compare(
            rest_string="""
                +---------------+
                | `table item`_ |
                +---------------+

                .. _table item: foo/bar
            """,
            html_string="""
                <table>
                <colgroup>
                <col width="100%" />
                </colgroup>
                <tr><td><a href="foo/bar">table item</a></td>
                </tr>
                </table>
            """
        )

    def test_link_in_table2(self):
        self.cross_compare(
            rest_string="""
                +-----------------------+
                | foo `table item`_ bar |
                +-----------------------+

                .. _table item: foo/bar
            """,
            html_string="""
                <table>
                <colgroup>
                <col width="100%" />
                </colgroup>
                <tr><td>foo <a href="foo/bar">table item</a> bar</td>
                </tr>
                </table>
            """
        )

    def test_link_in_table3(self):
        self.cross_compare(
            rest_string="""
                +-----------------------------+
                | * foo `table item 1`_ bar 1 |
                +-----------------------------+
                | * foo `table item 2`_ bar 2 |
                +-----------------------------+

                .. _table item 1: foo/bar/1/
                .. _table item 2: foo/bar/2/
            """,
            html_string="""
                <table>
                <colgroup>
                <col width="100%" />
                </colgroup>
                <tr><td><ul>
                <li>foo <a href="foo/bar/1/">table item 1</a> bar 1</li>
                </ul>
                </td>
                </tr>
                <tr><td><ul>
                <li>foo <a href="foo/bar/2/">table item 2</a> bar 2</li>
                </ul>
                </td>
                </tr>
                </table>
            """
        )

    def test_paragraph_bwlow_table_links(self):
        self.cross_compare(
            rest_string="""
                +-----------------+
                | `table item 1`_ |
                +-----------------+
                | `table item 2`_ |
                +-----------------+

                .. _table item 1: foo/bar/1/
                .. _table item 2: foo/bar/2/

                Text after table.
            """,
            html_string="""
                <table>
                <colgroup>
                <col width="100%" />
                </colgroup>
                <tr><td><a href="foo/bar/1/">table item 1</a></td>
                </tr>
                <tr><td><a href="foo/bar/2/">table item 2</a></td>
                </tr>
                </table>
                <p>Text after table.</p>
            """,
            # debug=True
        )

    def test_reuse_link_substitution1(self):
        self.cross_compare(
            rest_string="""
                +--------------------------------+
                | this is `foo bar`_ first time. |
                +--------------------------------+
                | and here `foo bar`_ again.     |
                +--------------------------------+

                .. _foo bar: foo/bar/

                Text after table.
            """,
            html_string="""
                <table>
                <colgroup>
                <col width="100%" />
                </colgroup>
                <tr><td>this is <a href="foo/bar/">foo bar</a> first time.</td>
                </tr>
                <tr><td>and here <a href="foo/bar/">foo bar</a> again.</td>
                </tr>
                </table>
                <p>Text after table.</p>
            """,
            # debug=True
        )

    def test_reuse_link_substitution2(self):
        self.cross_compare(
            rest_string="""
                +--------------------------------+
                | this is `foo bar`_ first time. |
                +--------------------------------+

                .. _foo bar: foo/bar/

                and here `foo bar`_ again, after table.
            """,
            html_string="""
                <table>
                <colgroup>
                <col width="100%" />
                </colgroup>
                <tr><td>this is <a href="foo/bar/">foo bar</a> first time.</td>
                </tr>
                </table>
                <p>and here <a href="foo/bar/">foo bar</a> again, after table.</p>
            """,
            # debug=True
        )

    def test_reuse_image_substitution(self):
        self.cross_compare(
            rest_string="""
                +----------------------+
                | first |image| here   |
                +----------------------+
                | second |image| there |
                +----------------------+

                .. |image| image:: /picture.png
            """,
            html_string="""
                <table>
                <colgroup>
                <col width="100%" />
                </colgroup>
                <tr><td>first <img alt="image" src="/picture.png" /> here</td>
                </tr>
                <tr><td>second <img alt="image" src="/picture.png" /> there</td>
                </tr>
                </table>
            """,
            # debug=True
        )

    def test_duplicate_image_substitution(self):
        self.cross_compare(
            rest_string="""
                +----------------------+
                | a |same| image here  |
                +----------------------+
                | a `same`_ link there |
                +----------------------+

                .. |same| image:: /image.png
                .. _same: /url/foo/

                again: the |same| image and `same`_ link!
            """,
            html_string="""
                <table>
                <colgroup>
                <col width="100%" />
                </colgroup>
                <tr><td>a <img alt="same" src="/image.png" /> image here</td>
                </tr>
                <tr><td>a <a href="/url/foo/">same</a> link there</td>
                </tr>
                </table>
                <p>again: the <img alt="same" src="/image.png" /> image and <a href="/url/foo/">same</a> link!</p>
            """,
            # debug=True
        )


#    def test_inline_literal(self):
#        """ TODO
#        http://docutils.sourceforge.net/docs/user/rst/quickref.html#inline-markup
#        """
#        self.cross_compare_rest(
#            rest_string="""
#                ``inline literal``
#            """,
#            html_string="""
#                <p><code>inline&nbsp;literal</code></p>
#            """
#        )

#    def test_escape_in_pre(self):
#        self.cross_compare_rest(
#            textile_string="""
#                <pre>
#                <html escaped>
#                </pre>
#            """,
#            html_string="""
#                <pre>
#                &#60;html escaped&#62;
#                </pre>
#            """)
if __name__ == '__main__':
    unittest.main(
        #        defaultTest="CrossCompareReStTests.test_paragraph_bwlow_table_links",
    )
