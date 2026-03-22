"""
    cross compare unittest
    ~~~~~~~~~~~~~~~~~~~~~~

    Compare all similarities between:
        * creole2html
        * html2creole
        * textile2html (used the python textile module)
        * html2textile

    Note: This only works fine if there is no problematic whitespace handling.
        In this case, we must test in test_creole2html.py or test_html2creole.py

    :copyleft: 2008-2014 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import unittest

from creole.tests.utils.base_unittest import BaseCreoleTest


class CrossCompareTests(BaseCreoleTest):
    """
    Cross compare tests for creol2html _and_ html2creole with the same test
    strings. Used BaseCreoleTest.assertCreole()
    """

    def test_bold_italics(self):
        self.cross_compare(
            creole_string=r"""
                **bold** //italics//
                //italics and **bold**.//
                **bold and //italics//.**
            """,
            html_string="""
                <p><strong>bold</strong> <i>italics</i><br />
                <i>italics and <strong>bold</strong>.</i><br />
                <strong>bold and <i>italics</i>.</strong></p>
            """,
        )
        self.cross_compare(
            textile_string="""
                *bold* __italics__
                __italics and *bold*.__
                *bold and __italics__.*
            """,
            html_string="""
                <p><strong>bold</strong> <i>italics</i><br />

                <i>italics and <strong>bold</strong>.</i><br />

                <strong>bold and <i>italics</i>.</strong></p>
            """,
        )
        # Note: In ReSt inline markup may not be nested.
        self.cross_compare(
            html_string="""
                <p><strong>bold</strong> <em>italics</em></p>
            """,
            rest_string="""
                **bold** *italics*
            """,
        )

    def test_bold_italics2(self):
        self.cross_compare(
            creole_string=r"""
                **//bold italics//**
                //**bold italics**//
                //This is **also** good.//
            """,
            html_string="""
                <p><strong><i>bold italics</i></strong><br />
                <i><strong>bold italics</strong></i><br />
                <i>This is <strong>also</strong> good.</i></p>
            """,
        )
        self.cross_compare(
            textile_string="""
                *__bold italics__*
                __*bold italics*__
                __This is *also* good.__
            """,
            html_string="""
                <p><strong><i>bold italics</i></strong><br />

                <i><strong>bold italics</strong></i><br />

                <i>This is <strong>also</strong> good.</i></p>
            """,
        )

    def test_headlines1(self):
        self.cross_compare(
            creole_string=r"""
                = Section Title 1

                == Section Title 2

                === Section Title 3

                ==== Section Title 4

                ===== Section Title 5

                ====== Section Title 6
            """,
            textile_string="""
                h1. Section Title 1

                h2. Section Title 2

                h3. Section Title 3

                h4. Section Title 4

                h5. Section Title 5

                h6. Section Title 6
            """,
            html_string="""
                <h1>Section Title 1</h1>

                <h2>Section Title 2</h2>

                <h3>Section Title 3</h3>

                <h4>Section Title 4</h4>

                <h5>Section Title 5</h5>

                <h6>Section Title 6</h6>
            """
        )
        self.cross_compare(
            rest_string="""
                ===============
                Section Title 1
                ===============

                ---------------
                Section Title 2
                ---------------

                Section Title 3
                ===============

                Section Title 4
                ---------------

                Section Title 5
                ```````````````

                Section Title 6
                '''''''''''''''
            """,
            html_string="""
                <h1>Section Title 1</h1>
                <h2>Section Title 2</h2>
                <h3>Section Title 3</h3>
                <h4>Section Title 4</h4>
                <h5>Section Title 5</h5>
                <h6>Section Title 6</h6>
            """
        )

    def test_horizontal_rule(self):
        all_markups = """
            Text before horizontal rule.

            ----

            Text after the line.
        """
        self.cross_compare(
            creole_string=all_markups,
            # textile_string=all_markups, # FIXME: textile and <hr> ?
            html_string="""
                <p>Text before horizontal rule.</p>

                <hr />

                <p>Text after the line.</p>
            """
        )
        self.cross_compare(
            rest_string=all_markups,
            html_string="""
                <p>Text before horizontal rule.</p>
                <hr />
                <p>Text after the line.</p>
            """
        )

    def test_link(self):
        self.cross_compare(
            creole_string=r"""
                X [[http://domain.tld|link B]] test.
            """,
            textile_string="""
                X "link B":http://domain.tld test.
            """,
            rest_string="""
                X `link B <http://domain.tld>`_ test.
            """,
            html_string="""
                <p>X <a href="http://domain.tld">link B</a> test.</p>
            """
        )

    def test_link_without_title(self):
        self.cross_compare(
            creole_string=r"""
                [[http://www.pylucid.org]]
            """,
            textile_string="""
                "http://www.pylucid.org":http://www.pylucid.org
            """,
            rest_string="""
                `http://www.pylucid.org <http://www.pylucid.org>`_
            """,
            html_string="""
                <p><a href="http://www.pylucid.org">http://www.pylucid.org</a></p>
            """
        )

    def test_link_with_unknown_protocol(self):
        self.cross_compare(
            creole_string=r"""
                X [[foo://bar|unknown protocol]] Y
            """,
            # textile will return '#' if url scheme is unknown!
            # textile_string="""
            #     X "unknown protocol":foo://bar Y
            # """,
            rest_string="""
                X `unknown protocol <foo://bar>`_ Y
            """,
            html_string="""
                <p>X <a href="foo://bar">unknown protocol</a> Y</p>
            """
        )

    def test_link_with_at_sign(self):
        self.cross_compare(
            creole_string=r"""
                X [[http://de.wikipedia.org/wiki/Creole_(Markup)|Creole@wikipedia]]
            """,
            html_string="""
                <p>X <a href="http://de.wikipedia.org/wiki/Creole_(Markup)">Creole@wikipedia</a></p>
            """
        )
        self.cross_compare(
            rest_string="""
                X `Creole@wikipedia <http://de.wikipedia.org/wiki/Creole_(Markup)>`_
            """,
            html_string="""
                <p>X <a href="http://de.wikipedia.org/wiki/Creole_(Markup)">Creole&#64;wikipedia</a></p>
            """
        )
        self.cross_compare_textile(
            textile_string="""
                X "foo@domain":http://domain.tld
            """,
            html_string="""
                <p>X <a href="http://domain.tld">foo@domain</a></p>
            """
        )

    def test_image(self):
        self.cross_compare(
            creole_string=r"""
                a {{/image.jpg|JPG pictures}} and
                a {{/image.jpeg|JPEG pictures}} and
                a {{/image.gif|GIF pictures}} and
                a {{/image.png|PNG pictures}} !
                {{/path1/path2/image|Image without files ext?}}
            """,
            html_string="""
                <p>a <img src="/image.jpg" title="JPG pictures" alt="JPG pictures" /> and<br />
                a <img src="/image.jpeg" title="JPEG pictures" alt="JPEG pictures" /> and<br />
                a <img src="/image.gif" title="GIF pictures" alt="GIF pictures" /> and<br />
                a <img src="/image.png" title="PNG pictures" alt="PNG pictures" /> !<br />
                <img src="/path1/path2/image" title="Image without files ext?" alt="Image without files ext?" /></p>
            """
        )
        self.cross_compare(
            textile_string="""
                a !/image.jpg(JPG pictures)! and
                a !/image.jpeg(JPEG pictures)! and
                a !/image.gif(GIF pictures)! and
                a !/image.png(PNG pictures)! !
                !/path1/path2/image(Image without files ext?)!
            """,
            html_string="""
                <p>a <img alt="JPG pictures" src="/image.jpg" title="JPG pictures" /> and<br />

                a <img alt="JPEG pictures" src="/image.jpeg" title="JPEG pictures" /> and<br />

                a <img alt="GIF pictures" src="/image.gif" title="GIF pictures" /> and<br />

                a <img alt="PNG pictures" src="/image.png" title="PNG pictures" /> !<br />

                <img alt="Image without files ext?" src="/path1/path2/image" title="Image without files ext?" /></p>
            """
        )
        self.cross_compare(
            rest_string="""
                1 |JPG pictures| one

                .. |JPG pictures| image:: /image.jpg

                2 |JPEG pictures| two

                .. |JPEG pictures| image:: /image.jpeg

                3 |GIF pictures| tree

                .. |GIF pictures| image:: /image.gif

                4 |PNG pictures| four

                .. |PNG pictures| image:: /image.png

                5 |Image without files ext?| five

                .. |Image without files ext?| image:: /path1/path2/image
            """,
            html_string="""
                <p>1 <img alt="JPG pictures" src="/image.jpg" /> one</p>
                <p>2 <img alt="JPEG pictures" src="/image.jpeg" /> two</p>
                <p>3 <img alt="GIF pictures" src="/image.gif" /> tree</p>
                <p>4 <img alt="PNG pictures" src="/image.png" /> four</p>
                <p>5 <img alt="Image without files ext?" src="/path1/path2/image" /> five</p>
            """
        )

    def test_link_image(self):
        """ FIXME: ReSt. and linked images """
        self.cross_compare(
            creole_string=r"""
                Linked [[http://example.com/|{{myimage.jpg|example site}} image]]
            """,
            html_string="""
                <p>Linked <a href="http://example.com/"><img src="myimage.jpg" title="example site" alt="example site" /> image</a></p>
            """
        )
        self.cross_compare(
            textile_string="""
                Linked "!myimage.jpg(example site)! image":http://example.com/
            """,
            html_string="""
                <p>Linked <a href="http://example.com/"><img alt="example site" src="myimage.jpg" title="example site" /> image</a></p>
            """
        )


#        self.cross_compare(# FIXME: ReSt
#            rest_string="""
#                I recommend you try |PyLucid CMS|_.
#
#                .. |PyLucid CMS| image:: /images/pylucid.png
#                .. _PyLucid CMS: http://www.pylucid.org/
#            """,
#            html_string="""
#                <p>I recommend you try <a href="http://www.pylucid.org/"><img alt="PyLucid CMS" src="/images/pylucid.png" /></a>.</p>
#            """
#        )

    def test_pre1(self):
        self.cross_compare(
            creole_string=r"""
                {{{
                * no list
                }}}
                """,
            textile_string="""
                <pre>
                * no list
                </pre>
                """,
            html_string="""
                <pre>
                * no list
                </pre>
            """)
        self.cross_compare(  # FIXME: Not the best html2rest output
            rest_string="""
                Preformatting text:

                ::

                    Here some performatting with
                    no `link <http://domain.tld>`_ here.
                    text... end.

                Under pre block
            """,
            html_string="""
                <p>Preformatting text:</p>
                <pre>
                Here some performatting with
                no `link &lt;http://domain.tld&gt;`_ here.
                text... end.
                </pre>
                <p>Under pre block</p>
            """
        )


#    def test_pre2(self):
#        """ TODO: html2creole: wrong lineendings """
#        self.cross_compare(
#            creole_string=r"""
#                start
#
#                {{{
#                * no list
#                }}}
#
#                end
#                """,
#            textile_string="""
#                start
#
#                <pre>
#                * no list
#                </pre>
#
#                end
#                """,
#            html_string="""
#                <p>start</p>
#
#                <pre>
#                * no list
#                </pre>
#
#                <p>end</p>
#            """)

    def test_pre_contains_braces(self):
        self.cross_compare(
            creole_string="""
                {{{
                # Closing braces in nowiki:
                if (x != NULL) {
                  for (i = 0) {
                    if (x = 1) {
                      x[i]--;
                  }}}
                }}}
                """,
            textile_string="""
                <pre>
                # Closing braces in nowiki:
                if (x != NULL) {
                  for (i = 0) {
                    if (x = 1) {
                      x[i]--;
                  }}}
                </pre>
                """,
            rest_string="""
                ::

                    # Closing braces in nowiki:
                    if (x != NULL) {
                      for (i = 0) {
                        if (x = 1) {
                          x[i]--;
                      }}}
                """,
            html_string="""
                <pre>
                # Closing braces in nowiki:
                if (x != NULL) {
                  for (i = 0) {
                    if (x = 1) {
                      x[i]--;
                  }}}
                </pre>
            """)

    def test_list(self):
        """ Bold, Italics, Links, Pre in Lists """
        self.cross_compare(
            creole_string=r"""
                * **bold** item
                * //italic// item

                # item about a [[/foo/bar|certain_page]]
                """,
            textile_string="""
                * *bold* item
                * __italic__ item

                # item about a "certain_page":/foo/bar
            """,
            html_string="""
                <ul>
                  <li><strong>bold</strong> item</li>
                  <li><i>italic</i> item</li>
                </ul>
                <ol>
                  <li>item about a <a href="/foo/bar">certain_page</a></li>
                </ol>
            """,
            strip_lines=True
        )

    def test_simple_table(self):
        self.cross_compare(
            creole_string="""
                |= Headline 1 |= Headline 2 |
                | cell one    | cell two    |
                """,
            textile_string="""
                |_. Headline 1|_. Headline 2|
                |cell one|cell two|
                """,
            html_string="""
                <table>
                <tr>
                    <th>Headline 1</th>
                    <th>Headline 2</th>
                </tr>
                <tr>
                    <td>cell one</td>
                    <td>cell two</td>
                </tr>
                </table>
            """,
            # debug=True
            strip_lines=True,
        )
        self.cross_compare(
            rest_string="""
                +------------+------------+
                | Headline 1 | Headline 2 |
                +============+============+
                | cell one   | cell two   |
                +------------+------------+
                """,
            html_string="""
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
            """,
            # debug=True
        )


if __name__ == '__main__':
    unittest.main()
