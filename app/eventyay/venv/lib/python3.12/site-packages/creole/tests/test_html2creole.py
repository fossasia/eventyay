"""
    html2creole tests
    ~~~~~~~~~~~~~~~~~

    special html to creole convert tests, witch can't tests in "cross compare"


    :copyleft: 2008-2011 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import unittest

from creole import html2creole
from creole.shared.unknown_tags import (
    escape_unknown_nodes,
    raise_unknown_node,
    transparent_unknown_nodes,
    use_html_macro,
)
from creole.tests.utils.base_unittest import BaseCreoleTest


class TestHtml2Creole(unittest.TestCase):
    """
    Tests around html2creole API.
    """
    pass


class TestHtml2CreoleMarkup(BaseCreoleTest):

    #    def assertCreole(self, raw_markup, raw_html, debug=False, **kwargs):
    #        self.assert_html2creole(raw_markup, raw_html, debug=debug, **kwargs)

    # --------------------------------------------------------------------------

    def test_not_used(self):
        """
        Some other html tags -> convert.
        """
        self.assert_html2creole(r"""
            **Bold text**
            **Big text**
            //em tag//
            //italic//
        """, """
            <p><b>Bold text</b><br />
            <big>Big text</big><br />
            <em>em tag</em><br />
            <i>italic</i></p>
        """)

    # --------------------------------------------------------------------------

    def test_raise_unknown_node(self):
        """
        Test creole.html2creole.raise_unknown_node callable:
        Raise NotImplementedError on unknown tags.
        """
        self.assertRaises(NotImplementedError,
                          html2creole,
                          html_string="<unknwon>",
                          unknown_emit=raise_unknown_node
                          )

    def test_use_html_macro(self):
        """
        Test creole.html2creole.use_html_macro callable:
        Use the <<html>> macro to mask unknown tags.
        """
        self.assert_html2creole(r"""
            111 <<html>><unknown><</html>>foo<<html>></unknown><</html>> 222
            333<<html>><unknown foo1="bar1" foo2="bar2"><</html>>foobar<<html>></unknown><</html>>444

            555<<html>><unknown /><</html>>666
        """, """
            <p>111 <unknown>foo</unknown> 222<br />
            333<unknown foo1="bar1" foo2="bar2">foobar</unknown>444</p>

            <p>555<unknown />666</p>
        """,
                                unknown_emit=use_html_macro
                                )

    def test_escape_unknown_nodes(self):
        """
        Test creole.html2creole.escape_unknown_nodes callable:
        All unknown tags should be escaped.
        """
        self.assert_html2creole(r"""
            111 &lt;unknown&gt;foo&lt;/unknown&gt; 222
            333&lt;unknown foo1="bar1" foo2="bar2"&gt;foobar&lt;/unknown&gt;444

            555&lt;unknown /&gt;666
        """, """
            <p>111 <unknown>foo</unknown> 222<br />
            333<unknown foo1="bar1" foo2="bar2">foobar</unknown>444</p>

            <p>555<unknown />666</p>
        """,
                                unknown_emit=escape_unknown_nodes
                                )

    def test_escape_unknown_nodes2(self):
        """
        HTMLParser has problems with <script> tags.
        See: http://bugs.python.org/issue670664
        """
        self.assert_html2creole(r"""
            &lt;script&gt;var js_sha_link='<p>***</p>';&lt;/script&gt;
        """, """
            <script>
            var js_sha_link='<p>***</p>';
            </script>
        """,
                                unknown_emit=escape_unknown_nodes
                                )

    def test_transparent_unknown_nodes(self):
        """
        Test creole.html2creole.transparent_unknown_nodes callable:
        All unknown tags should be "transparent" and show only
        their child nodes' content.
        """
        self.assert_html2creole(r"""
            //baz//, **quux**
        """, """
            <form class="foo" id="bar"><label><em>baz</em></label>, <strong>quux</strong></form>
        """, unknown_emit=transparent_unknown_nodes
                                )

    def test_transparent_unknown_nodes2(self):
        """
        HTMLParser has problems with <script> tags.
        See: http://bugs.python.org/issue670664
        """
        self.assert_html2creole(r"""
            FOO var a='<em>STRONG</em>'; BAR
        """, """
            <p>FOO <script>var a='<em>STRONG</em>';</script> BAR</p>
        """, unknown_emit=transparent_unknown_nodes
                                )

    def test_transparent_unknown_nodes_block_elements(self):
        """
        Test that block elements insert linefeeds into the stream.
        """
        self.assert_html2creole(r"""
            //baz//,

            **quux**

            spam, ham, and eggs
        """, """
            <div><em>baz</em>,</div> <fieldset><strong>quux</strong></fieldset>
            <span>spam, </span><label>ham, </label>and eggs
        """, unknown_emit=transparent_unknown_nodes
                                )

    # --------------------------------------------------------------------------

    def test_entities(self):
        """
        Test html entities.

        copyright sign is in Latin-1 Supplement:
            http://pylucid.org/_command/144/DecodeUnicode/display/1/
        Box Drawing:
            http://pylucid.org/_command/144/DecodeUnicode/display/66/
        """
        self.assert_html2creole("""
            * less-than sign: < < <
            * greater-than sign: > > >
            * copyright sign: © ©
            * box drawing: ╬ ╬
            * german umlauts: ä ö ü
        """, """
            <ul>
            <li>less-than sign: &lt; &#60; &#x3C;</li>
            <li>greater-than sign: &gt; &#62; &#x3E;</li>
            <li>copyright sign: &#169; &#xA9;</li>
            <li>box drawing: &#9580; &#x256C;</li>
            <li>german umlauts: &auml; &ouml; &uuml;</li>
            </ul>
        """)

    def test_html_entity_nbsp(self):
        """ Non breaking spaces is not in htmlentitydefs """
        self.assert_html2creole(r"""
            a non braking space: [ ] !
        """, """
            <p>a non braking space: [&nbsp;] !</p>
        """)

    def test_html_entity_in_pre(self):
        self.assert_html2creole(r"""
            {{{<code>{% lucidTag RSS url="http url" %}</code>}}}
        """, """
            <pre><code>&#x7B;% lucidTag RSS url="http url" %&#x7D;</code></pre>
        """)

    def test_unknown_entity(self):
        """
        Test a unknown html entity.
        FIXME: What sould happend?
        """
        self.assert_html2creole(r"""
            copy&paste
        """, """
            <p>copy&paste</p>
        """)
        self.assert_html2creole(r"""
            [[/url/|Search & Destroy]]
        """, """
            <a href="/url/">Search & Destroy</a>
        """)

    def test_tbody_table(self):
        self.assert_html2creole(r"""
            Ignore 'tbody' tag in tables:

            |= Headline 1 |= Headline 2 |
            | cell one    | cell two    |
            end
        """, """
            <p>Ignore 'tbody' tag in tables:</p>
            <table>
            <tbody>
            <tr>
                <th>Headline 1</th>
                <th>Headline 2</th>
            </tr>
            <tr>
                <td>cell one</td>
                <td>cell two</td>
            </tr>
            </tbody>
            </table>
            <p>end</p>
        """)

    def test_p_table(self):
        """ strip <p> tags in table cells """
        self.assert_html2creole(r"""
            | cell one | cell two\\new line |
        """, """
            <table>
            <tr>
                <td><p>cell one</p></td>
                <td><p>cell two</p><p>new line</p><p></p></td>
            </tr>
            </table>
        """)

    def test_image(self):
        """ test image tag with different alt/title attribute """
        self.assert_html2creole(r"""
            {{foobar1.jpg|foobar1.jpg}}
            {{/foobar2.jpg|foobar2.jpg}}
            {{/path1/path2/foobar3.jpg|foobar3.jpg}}
            {{/foobar4.jpg|It's foobar 4}}
            {{/foobar5.jpg|It's foobar 5}}
            {{/foobar6.jpg|a long picture title}}
        """, """
            <p><img src="foobar1.jpg" /><br />
            <img src="/foobar2.jpg" /><br />
            <img src="/path1/path2/foobar3.jpg" /><br />
            <img src="/foobar4.jpg" alt="It's foobar 4" /><br />
            <img src="/foobar5.jpg" title="It's foobar 5" /><br />
            <img src="/foobar6.jpg" alt="short name" title="a long picture title" /><br />
            <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA
            AAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO
            9TXL0Y4OHwAAAABJRU5ErkJggg==" alt="data uri should be disallowed" /></p>
        """)

    def test_image_with_size(self):
        """ test image tag with sizes """
        self.assert_html2creole(r"""
            {{foobar1.jpg|foobar1.jpg}}
            {{foobar2.jpg|foobar2.jpg|90x160}}
            {{foobar3.jpg|foobar3.jpg}}
        """, """
            <p><img src="foobar1.jpg" /><br />
            <img src="foobar2.jpg" width="160" height="90" /><br />
            <img src="foobar3.jpg" width="160" /></p>
        """)

    def test_image_with_size_strict(self):
        """ test image tag with sizes """
        self.assert_html2creole(r"""
            {{foobar1.jpg|foobar1.jpg}}
            {{foobar2.jpg|foobar2.jpg}}
            {{foobar3.jpg|foobar3.jpg}}
        """, """
            <p><img src="foobar1.jpg" /><br />
            <img src="foobar2.jpg" width="160" height="90" /><br />
            <img src="foobar3.jpg" width="160" /></p>
        """, strict=True)

    def test_non_closed_br(self):
        self.assert_html2creole(r"""
            one
            two
        """, """
            <p>one<br>
            two</p>
        """)

    def test_explicit_closed_br(self):
        self.assert_html2creole(r"""
            one
            two
        """, """
            <p>one<br></br>
            two</p>
        """)

    def test_newline_before_list(self):
        """
        http://code.google.com/p/python-creole/issues/detail?id=16
        """
        self.assert_html2creole(r"""
            **foo**

            * one
        """, """
            <b>foo</b><ul><li>one</li></ul>
        """)

    def test_empty_tags_are_not_escaped(self):
        self.assert_html2creole(r"""
            //baz//, **quux**
        """, """
            <div class="foo" id="bar"><span><em>baz</em></span>, <strong>quux</strong></div>
        """)

    def test_nested_listsitems_with_paragraph(self):
        self.assert_html2creole("""
            * item 1
            ** subitem 1.1
            *** subsubitem 1.1.1
            *** subsubitem 1.1.2
            ** subitem 1.2
            * item 2
            ** subitem 2.1
            """, """
            <ul>
                <li><p>item 1</p>
                    <ul>
                        <li><p>subitem 1.1</p>
                            <ul>
                                <li>subsubitem 1.1.1</li>
                                <li>subsubitem 1.1.2</li>
                            </ul>
                        </li>
                            <li><p>subitem 1.2</p></li>
                    </ul>
                </li>
                <li><p>item 2</p>
                    <ul>
                        <li>subitem 2.1</li>
                    </ul>
                </li>
            </ul>
        """)

    def test_class_in_list(self):
        """https://code.google.com/p/python-creole/issues/detail?id=19#c4"""
        self.assert_html2creole(r"""
            # foo
        """, """
            <ol class=gbtc><li>foo</li></ol>
        """)  # , debug=True)

    def test_ignore_links_without_href(self):
        """https://code.google.com/p/python-creole/issues/detail?id=19#c4"""
        self.assert_html2creole(r"""
            bar
        """, """
            <a class="foo">bar</a>
        """)  # , debug=True)

    def test_newlines_after_headlines(self):
        self.assert_html2creole(r"""
            = Headline news

            [[http://google.com|The googlezor]] is a big bad mother.
        """, """
            <h1>Headline news</h1>

            <p><a href="http://google.com">The googlezor</a> is a big bad mother.</p>
        """)

    def test_links(self):
        self.assert_html2creole(r"""
            test link: '[[internal links|link A]]' 1 and
            test link: '[[http://domain.tld|link B]]' 2.
        """, """
            <p>test link: '<a href="internal links">link A</a>' 1 and<br />
            test link: '<a href="http://domain.tld">link B</a>' 2.</p>
        """)

    def test_horizontal_rule(self):
        self.assert_html2creole(r"""
            one

            ----

            two
        """, """
            <p>one</p>
            <hr />
            <p>two</p>
        """)

    def test_nested_empty_tags(self):
        self.assert_html2creole2("TEST", "<p>TEST</p>")
        self.assert_html2creole2("TEST", "<bar><p>TEST</p></bar>")
        self.assert_html2creole2("TEST", "<foo><bar><p>TEST</p></bar></foo>")


#    def test_nowiki1(self):
#        self.assert_html2creole(r"""
#            this:
#            {{{
#            //This// does **not** get [[formatted]]
#            }}}
#            and this: {{{** <i>this</i> ** }}} not, too.
#
#            === Closing braces in nowiki:
#            {{{
#            if (x != NULL) {
#              for (i = 0; i < size; i++) {
#                if (x[i] > 0) {
#                  x[i]--;
#              }}}
#            }}}
#        """, """
#            <p>this:</p>
#            <pre>
#            //This// does **not** get [[formatted]]
#            </pre>
#            <p>and this: <tt>** &lt;i&gt;this&lt;/i&gt; ** </tt> not, too.</p>
#
#            <h3>Closing braces in nowiki:</h3>
#            <pre>
#            if (x != NULL) {
#              for (i = 0; i &lt; size; i++) {
#                if (x[i] &gt; 0) {
#                  x[i]--;
#              }}}
#            </pre>
#        """)
#
#    def test_list1(self):
#        """
#        FIXME: Two newlines between a list and the next paragraph :(
#        """
#        self.assert_html2creole(r"""
#            ==== List a:
#            * a1 item
#            ** a1.1 Force\\linebreak
#            ** a1.2 item
#            *** a1.2.1 item
#            *** a1.2.2 item
#            * a2 item
#
#
#            list 'a' end
#
#            ==== List b:
#            # b1 item
#            ## b1.2 item
#            ### b1.2.1 item
#            ### b1.2.2 Force\\linebreak1\\linebreak2
#            ## b1.3 item
#            # b2 item
#
#
#            list 'b' end
#        """, """
#            <h4>List a:</h4>
#            <ul>
#            <li>a1 item</li>
#            <ul>
#                <li>a1.1 Force
#                linebreak</li>
#                <li>a1.2 item</li>
#                <ul>
#                    <li>a1.2.1 item</li>
#                    <li>a1.2.2 item</li>
#                </ul>
#            </ul>
#            <li>a2 item</li>
#            </ul>
#            <p>list 'a' end</p>
#
#            <h4>List b:</h4>
#            <ol>
#            <li>b1 item</li>
#            <ol>
#                <li>b1.2 item</li>
#                <ol>
#                    <li>b1.2.1 item</li>
#                    <li>b1.2.2 Force
#                    linebreak1
#                    linebreak2</li>
#                </ol>
#                <li>b1.3 item</li>
#            </ol>
#            <li>b2 item</li>
#            </ol>
#            <p>list 'b' end</p>
#        """,
# debug=True
#        )
#
#    def test_list2(self):
#        """ Bold, Italics, Links, Pre in Lists """
#        self.assert_html2creole(r"""
#            * **bold** item
#            * //italic// item
#
#            # item about a [[domain.tld|page link]]
#            # {{{ //this// is **not** [[processed]] }}}
#        """, """
#            <ul>
#                <li><strong>bold</strong> item</li>
#                <li><i>italic</i> item</li>
#            </ul>
#            <ol>
#                <li>item about a <a href="domain.tld">page link</a></li>
#                <li><tt>//this// is **not** [[processed]]</tt></li>
#            </ol>
#        """,
# debug=True
#        )


if __name__ == '__main__':
    unittest.main(
        #        defaultTest="TestHtml2CreoleMarkup.test_nested_listsitems_with_paragraph"
    )
