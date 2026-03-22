"""
    Unittest which failed, cause bugfixes not implemented, yet.
"""

import unittest

from creole.html_tools.strip_html import strip_html
from creole.tests.utils.base_unittest import BaseCreoleTest


class StripHtml(unittest.TestCase):
    @unittest.expectedFailure
    def test_not_closed_image_tag(self):
        output = strip_html('<p>a <img src="/image.jpg"> image.</p>')
        self.assertEqual(output, '<p>a <img src="/image.jpg"> image.</p>')

    @unittest.expectedFailure
    def test_remove_linebreak(self):
        output = strip_html('<strong>foo</strong>\n<ul><li>one</li></ul>')
        self.assertEqual(output, '<strong>foo</strong><ul><li>one</li></ul>')


class CrossCompareCreoleTests(BaseCreoleTest):
    @unittest.expectedFailure
    def test_cross_lines_creole2html(self):
        """ TODO: bold/italics cross lines in creole2html
        see: http://code.google.com/p/python-creole/issues/detail?id=13
        Info: The way html2creole works, see above
        """
        self.cross_compare_creole(
            creole_string=r"""
                Bold and italics should //be
                able// to **cross
                lines.**
            """,
            html_string="""
                <p>Bold and italics should <i>be<br />
                able</i> to <strong>cross<br />
                lines.</strong></p>
            """
        )

    @unittest.expectedFailure
    def test_cross_paragraphs(self):
        """ TODO: bold/italics cross paragraphs in creole2html
        see: http://code.google.com/p/python-creole/issues/detail?id=13
        """
        self.assert_creole2html("""
            But, should //not be...

            ...able// to cross paragraphs.
        """, """
            <p>But, should <em>not be...</em></p>
            <p>...able<em> to cross paragraphs.</em></p>
        """)

    @unittest.expectedFailure
    def test_escape_inline(self):
        """ TODO: different pre/code syntax?
        """
        self.cross_compare_creole(r"""
            this is {{{**escaped** inline}}}, isn't it?

            {{{
            a **code**
            block
            }}}
        """, """
            <p>this is <tt>**escaped** inline</tt>, isn't it?</p>

            <pre>
            a **code**
            block
            </pre>
        """)


class TestHtml2CreoleMarkup(BaseCreoleTest):
    @unittest.expectedFailure
    def test_format_in_a_text(self):
        """ TODO: http://code.google.com/p/python-creole/issues/detail?id=4 """
        self.assert_html2creole(r"""
            **[[/url/|title]]**
        """, """
            <a href="/url/"><strong>title</strong></a>
        """)

    @unittest.expectedFailure
    def test_newline_before_headline(self):
        """ TODO: http://code.google.com/p/python-creole/issues/detail?id=16#c5 """
        self.assert_html2creole(r"""
            **foo**

            = one
        """, """
            <b>foo</b>
            <h1>one</h1>
        """)  # , debug=True)

    @unittest.expectedFailure
    def test_no_space_before_blocktag(self):
        """ TODO: Bug in html2creole.strip_html(): Don't add a space before/after block tags """
        self.assert_html2creole(r"""
            **foo**

            * one
        """, """
            <b>foo</b>
            <ul><li>one</li></ul>
        """  # , debug=True
                                )

    @unittest.expectedFailure
    def test_escape_char(self):
        self.assert_html2creole(r"""
            ~#1
            http://domain.tld/~bar/
            ~http://domain.tld/
            [[Link]]
            ~[[Link]]
        """, """
            <p>#1<br />
            <a href="http://domain.tld/~bar/">http://domain.tld/~bar/</a><br />
            http://domain.tld/<br />
            <a href="Link">Link</a><br />
            [[Link]]</p>
        """)

    @unittest.expectedFailure
    def test_images(self):
        self.assert_html2creole(r"""
            a {{/image.jpg|JPG pictures}} and
            a {{/image.jpeg|JPEG pictures}} and
            a {{/image.gif|GIF pictures}} and
            a {{/image.png|PNG pictures}} !

            picture [[www.domain.tld|{{foo.JPG|Foo}}]] as a link
        """, """
            <p>a <img src="/image.jpg" alt="JPG pictures"> and<br />
            a <img src="/image.jpeg" alt="JPEG pictures"> and<br />
            a <img src="/image.gif" alt="GIF pictures" /> and<br />
            a <img src="/image.png" alt="PNG pictures" /> !</p>

            <p>picture <a href="www.domain.tld"><img src="foo.JPG" alt="Foo"></a> as a link</p>
        """  # , debug=True
                                )
