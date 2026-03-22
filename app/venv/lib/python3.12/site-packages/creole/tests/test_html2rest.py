"""
    html2rest unittest
    ~~~~~~~~~~~~~~~~~~~~~

    Unittests for special cases which only works in the html2rest way.

    Note: This only works fine if there is no problematic whitespace handling.

    :copyleft: 2011-2012 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import unittest

from creole.emitter.html2rest_emitter import Html2restException
from creole.tests.utils.base_unittest import BaseCreoleTest


class ReStTests(BaseCreoleTest):
    def test_line_breaks(self):
        """
        Line breaks in HTML are lost.
        """
        self.assert_html2rest(
            rest_string="""
                first block, line 1 and line 2

                second block, line 1 and line 2
            """,
            html_string="""
                <p>first block, line 1
                and line 2</p>
                <p>second block, line 1
                and line 2</p>
            """,
            # debug=True
        )

    def test_substitution_image_without_alt_or_title(self):
        self.assert_html2rest(
            rest_string="""
                A inline |image.png| image.

                .. |image.png| image:: /url/to/image.png

                ...and some text below.
            """,
            html_string="""
                <p>A inline <img src="/url/to/image.png" /> image.</p>
                <p>...and some text below.</p>
            """
        )

    def test_substitution_image_with_title(self):
        self.assert_html2rest(
            rest_string="""
                A inline |foo bar| image.

                .. |foo bar| image:: /url/to/image.png

                ...and some text below.
            """,
            html_string="""
                <p>A inline <img title="foo bar" src="/url/to/image.png" /> image.</p>
                <p>...and some text below.</p>
            """
        )

    def test_substitution_image_without_p(self):
        self.assert_html2rest(
            rest_string="""
                |image.png|

                .. |image.png| image:: /url/to/image.png
            """,
            html_string="""
                <img src="/url/to/image.png" />
            """
        )

    def test_pre_code1(self):
        self.assert_html2rest(
            rest_string="""
                Text line

                ::

                    >>> from creole import creole2html
                    >>> creole2html("This is **creole //markup//**")
                    '<p>This is <strong>creole <i>markup</i></strong></p>'
            """,
            html_string="""
                <p>Text line</p>
                <pre>
                &gt;&gt;&gt; from creole import creole2html
                &gt;&gt;&gt; creole2html(&quot;This is **creole //markup//**&quot;)
                '&lt;p&gt;This is &lt;strong&gt;creole &lt;i&gt;markup&lt;/i&gt;&lt;/strong&gt;&lt;/p&gt;'
                </pre>
            """
        )

    def test_escape(self):
        self.assert_html2rest(
            rest_string="""
                * Use <tt> when {{{ ... }}} is inline and not <pre>, or not?
            """,
            html_string="""
                <ul>
                <li>Use &lt;tt&gt; when {{{ ... }}} is inline and not &lt;pre&gt;, or not?</li>
                </ul>
            """
        )

    def test_inline_literals(self):
        self.assert_html2rest(
            rest_string="""
                This text is an example of ``inline literals``.
            """,
            html_string="""
                <ul>
                <p>This text is an example of <tt>inline literals</tt>.</p>
                </ul>
            """
        )

    def test_list_without_p(self):
        self.assert_html2rest(
            rest_string="""
                A nested bullet lists:

                * item 1 without p-tag

                    * A **`subitem 1.1 </1.1/url/>`_ link** here.

                        * subsubitem 1.1.1

                        * subsubitem 1.1.2

                    * subitem 1.2

                * item 2 without p-tag

                    * subitem 2.1

                Text under list.
            """,
            html_string="""
                <p>A nested bullet lists:</p>
                <ul>
                    <li>item 1 without p-tag
                        <ul>
                            <li>A <strong><a href="/1.1/url/">subitem 1.1</a> link</strong> here.
                                <ul>
                                    <li>subsubitem 1.1.1</li>
                                    <li>subsubitem 1.1.2</li>
                                </ul>
                            </li>
                            <li>subitem 1.2</li>
                        </ul>
                    </li>
                    <li>item 2 without p-tag
                        <ul>
                            <li>subitem 2.1</li>
                        </ul>
                    </li>
                </ul>
                <p>Text under list.</p>
            """
        )

    def test_table_with_headings(self):
        self.assert_html2rest(
            rest_string="""
                +--------+--------+
                | head 1 | head 2 |
                +========+========+
                | item 1 | item 2 |
                +--------+--------+
            """,
            html_string="""
                <table>
                <tr><th>head 1</th><th>head 2</th>
                </tr>
                <tr><td>item 1</td><td>item 2</td>
                </tr>
                </table>
            """
        )

    def test_table_without_headings(self):
        self.assert_html2rest(
            rest_string="""
                +--------+--------+
                | item 1 | item 2 |
                +--------+--------+
                | item 3 | item 4 |
                +--------+--------+
            """,
            html_string="""
                <table>
                <tr><td>item 1</td><td>item 2</td>
                </tr>
                <tr><td>item 3</td><td>item 4</td>
                </tr>
                </table>
            """
        )

    def test_duplicate_substitution1(self):
        self.assertRaises(Html2restException, self.assert_html2rest,
                          rest_string="""
                +-----------------------------+
                | this is `same`_ first time. |
                +-----------------------------+

                .. _same: /first/

                the `same </other/>`_ link?
            """,
                          html_string="""
                <table>
                <tr><td>the <a href="/first/">same</a> first time.</td>
                </tr>
                </table>
                <p>the <a href="/other/">same</a> link?</p>
            """,
                          # debug=True
                          )

    def test_duplicate_link_substitution(self):
        self.assertRaises(Html2restException, self.assert_html2rest,
                          #        self.cross_compare(
                          rest_string="""
                +-----------------------------+
                | this is `same`_ first time. |
                +-----------------------------+

                .. _same: /first/

                the `same </other/>`_ link?
            """,
                          html_string="""
                <table>
                <tr><td>the <a href="/first/">same</a> first time.</td>
                </tr>
                </table>
                <p>the <a href="/other/">same</a> link?</p>
            """,
                          # debug=True
                          )

    def test_duplicate_image_substitution(self):
        self.assertRaises(Html2restException, self.assert_html2rest,
                          #        self.cross_compare(
                          rest_string="""
                a |image|...
                and a other |image|!

                .. |image| image:: /image.png
                .. |image| image:: /other.png
            """,
                          html_string="""
                <p>a <img src="/image.png" title="image" alt="image" />...<br />
                and a other <img src="/other.png" title="image" alt="image" />!</p>
            """,
                          # debug=True
                          )


#    def test_preformat_unknown_nodes(self):
#        """
#        Put unknown tags in a <pre> area.
#        """
#        self.assert_html2rest(
#            rest_string="""
#                111 <<pre>><x><</pre>>foo<<pre>></x><</pre>> 222
#                333<<pre>><x foo1="bar1"><</pre>>foobar<<pre>></x><</pre>>444
#
#                555<<pre>><x /><</pre>>666
#            """,
#            html_string="""
#                <p>111 <x>foo</x> 222<br />
#                333<x foo1="bar1">foobar</x>444</p>
#
#                <p>555<x />666</p>
#            """,
#            emitter_kwargs={"unknown_emit":preformat_unknown_nodes}
#        )
#
#    def test_transparent_unknown_nodes(self):
#        """
#        transparent_unknown_nodes is the default unknown_emit:
#
#        Remove all unknown html tags and show only
#        their child nodes' content.
#        """
#        self.assert_html2rest(
#            rest_string="""
#                111 <<pre>><x><</pre>>foo<<pre>></x><</pre>> 222
#                333<<pre>><x foo1="bar1"><</pre>>foobar<<pre>></x><</pre>>444
#
#                555<<pre>><x /><</pre>>666
#            """,
#            html_string="""
#                <p>111 <x>foo</x> 222<br />
#                333<x foo1="bar1">foobar</x>444</p>
#
#                <p>555<x />666</p>
#            """,
#        )

if __name__ == '__main__':
    unittest.main()
