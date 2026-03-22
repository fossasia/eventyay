"""
    cross compare creole unittest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Compare all similarities between:
        * creole2html
        * html2creole

    Note: This only works fine if there is no problematic whitespace handling.
        In this case, we must test in test_creole2html.py or test_html2creole.py

    :copyleft: 2008-2011 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import unittest

from creole.shared import example_macros
from creole.shared.unknown_tags import use_html_macro
from creole.tests.utils.base_unittest import BaseCreoleTest


class CrossCompareCreoleTests(BaseCreoleTest):
    def test_typeface(self):
        self.cross_compare_creole(
            creole_string=r"""
                basics:
                **//bold italics//**
                //**bold italics**//
                //This is **also** good.//

                Creole 1.0 optional:
                This is ##monospace## text.
                This is ^^superscripted^^ text.
                This is ,,subscripted,, text.
                This is __underlined__ text.

                own additions:
                This is --small-- and this ~~strikeout~~ ;)
            """,
            html_string="""
                <p>basics:<br />
                <strong><i>bold italics</i></strong><br />
                <i><strong>bold italics</strong></i><br />
                <i>This is <strong>also</strong> good.</i></p>

                <p>Creole 1.0 optional:<br />
                This is <tt>monospace</tt> text.<br />
                This is <sup>superscripted</sup> text.<br />
                This is <sub>subscripted</sub> text.<br />
                This is <u>underlined</u> text.</p>

                <p>own additions:<br />
                This is <small>small</small> and this <del>strikeout</del> ;)</p>
            """
        )

    def test_cross_lines_html2creole(self):
        """ bold/italics cross lines
        see: http://code.google.com/p/python-creole/issues/detail?id=13
        TODO: The way back creole2html doesn't work, see below
        """
        self.assert_html2creole(r"""
            Bold and italics should //be
            able// to **cross
            lines.**
        """, """
            <p>Bold and italics should <i>be<br />
            able</i> to <strong>cross<br />
            lines.</strong></p>
        """)

    def test_small(self):
        """
        http://code.google.com/p/python-creole/issues/detail?id=12#c0
        """
        self.cross_compare_creole(
            creole_string=r"""
                no -- small
                no // italics
                no ** bold
                no ## monospace
                no ^^ superscripted
                no ,, subscripted
                no __ underline
            """,
            html_string="""
                <p>no -- small<br />
                no // italics<br />
                no ** bold<br />
                no ## monospace<br />
                no ^^ superscripted<br />
                no ,, subscripted<br />
                no __ underline</p>
            """,
            debug=False
        )

    def test_link(self):
        self.cross_compare_creole(
            creole_string=r"""
                this is [[/a internal]] link.
                1 [[internal links|link A]] test.
            """,
            html_string="""
                <p>this is <a href="/a internal">/a internal</a> link.<br />
                1 <a href="internal links">link A</a> test.</p>
            """
        )

    def test_bolditalic_links(self):
        self.cross_compare_creole(r"""
            //[[a internal]]//
            **[[Shortcut2|a page2]]**
            //**[[Shortcut3|a page3]]**//
        """, """
            <p><i><a href="a internal">a internal</a></i><br />
            <strong><a href="Shortcut2">a page2</a></strong><br />
            <i><strong><a href="Shortcut3">a page3</a></strong></i></p>
        """)

    def test_pre_contains_braces(self):
        """
        braces, &gt and %lt in a pre area.
        """
        self.cross_compare_creole(
            creole_string=r"""
                === Closing braces in nowiki:

                {{{
                if (x != NULL) {
                  for (i = 0; i < size; i++) {
                    if (x[i] > 0) {
                      x[i]--;
                  }}}
                }}}
                """,
            html_string="""
                <h3>Closing braces in nowiki:</h3>

                <pre>
                if (x != NULL) {
                  for (i = 0; i &lt; size; i++) {
                    if (x[i] &gt; 0) {
                      x[i]--;
                  }}}
                </pre>
            """)

    def test_pre2(self):
        self.cross_compare_creole(r"""
            111

            {{{
            //This// does **not** get [[formatted]]
            }}}
            222

            one

            {{{
            foo

            bar
            }}}
            two
        """, """
            <p>111</p>

            <pre>
            //This// does **not** get [[formatted]]
            </pre>
            <p>222</p>

            <p>one</p>

            <pre>
            foo

            bar
            </pre>
            <p>two</p>
        """)

    def test_pre(self):
        self.cross_compare_creole(r"""
            start

            {{{
            * no list
            <html escaped>
            }}}
            end
        """, """
            <p>start</p>

            <pre>
            * no list
            &lt;html escaped&gt;
            </pre>
            <p>end</p>
        """)

    def test_tt(self):
        self.cross_compare_creole(r"""
            this is ##**strong** Teletyper## ;)
        """, """
            <p>this is <tt><strong>strong</strong> Teletyper</tt> ;)</p>
        """)

    def test_no_inline_headline(self):
        self.cross_compare_creole(
            creole_string=r"""
                = Headline

                === **not** //parsed//

                No == headline == or?
            """,
            html_string="""
                <h1>Headline</h1>

                <h3>**not** //parsed//</h3>

                <p>No == headline == or?</p>
            """
        )

    def test_horizontal_rule(self):
        self.cross_compare_creole(r"""
            one

            ----

            two
        """, """
            <p>one</p>

            <hr />

            <p>two</p>
        """)

    def test_bullet_list(self):
        self.cross_compare_creole(r"""
            * Item 1
            ** Item 1.1
            ** a **bold** Item 1.2
            * Item 2
            ** Item 2.1
            *** [[a link Item 3.1]]
            *** Force\\linebreak 3.2
            *** item 3.3
            *** item 3.4

            up to five levels

            * 1
            ** 2
            *** 3
            **** 4
            ***** 5
        """, """
            <ul>
                <li>Item 1
                <ul>
                    <li>Item 1.1</li>
                    <li>a <strong>bold</strong> Item 1.2</li>
                </ul></li>
                <li>Item 2
                <ul>
                    <li>Item 2.1
                    <ul>
                        <li><a href="a link Item 3.1">a link Item 3.1</a></li>
                        <li>Force<br />
                        linebreak 3.2</li>
                        <li>item 3.3</li>
                        <li>item 3.4</li>
                    </ul></li>
                </ul></li>
            </ul>
            <p>up to five levels</p>

            <ul>
                <li>1
                <ul>
                    <li>2
                    <ul>
                        <li>3
                        <ul>
                            <li>4
                            <ul>
                                <li>5</li>
                            </ul></li>
                        </ul></li>
                    </ul></li>
                </ul></li>
            </ul>
        """)

    def test_number_list(self):
        self.cross_compare_creole(r"""
            # Item 1
            ## Item 1.1
            ## a **bold** Item 1.2
            # Item 2
            ## Item 2.1
            ### [[a link Item 3.1]]
            ### Force\\linebreak 3.2
            ### item 3.3
            ### item 3.4

            up to five levels

            # 1
            ## 2
            ### 3
            #### 4
            ##### 5
        """, """
            <ol>
                <li>Item 1
                <ol>
                    <li>Item 1.1</li>
                    <li>a <strong>bold</strong> Item 1.2</li>
                </ol></li>
                <li>Item 2
                <ol>
                    <li>Item 2.1
                    <ol>
                        <li><a href="a link Item 3.1">a link Item 3.1</a></li>
                        <li>Force<br />
                        linebreak 3.2</li>
                        <li>item 3.3</li>
                        <li>item 3.4</li>
                    </ol></li>
                </ol></li>
            </ol>
            <p>up to five levels</p>

            <ol>
                <li>1
                <ol>
                    <li>2
                    <ol>
                        <li>3
                        <ol>
                            <li>4
                            <ol>
                                <li>5</li>
                            </ol></li>
                        </ol></li>
                    </ol></li>
                </ol></li>
            </ol>
        """,
                                  #        debug = True
                                  )

    def test_big_table(self):
        self.cross_compare_creole(r"""
            A Table...

            |= Headline  |= a other\\headline    |= the **big end**     |
            | a cell     | a **big** cell        | **//bold italics//** |
            | next\\line | No == headline == or? |                      |
            | link test: | a [[/url/|link]] in   | a cell.              |
            |            |                       | empty cells          |
            ...end
        """, """
            <p>A Table...</p>

            <table>
            <tr>
                <th>Headline</th>
                <th>a other<br />
                    headline</th>
                <th>the <strong>big end</strong></th>
            </tr>
            <tr>
                <td>a cell</td>
                <td>a <strong>big</strong> cell</td>
                <td><strong><i>bold italics</i></strong></td>
            </tr>
            <tr>
                <td>next<br />
                    line</td>
                <td>No == headline == or?</td>
                <td></td>
            </tr>
            <tr>
                <td>link test:</td>
                <td>a <a href="/url/">link</a> in</td>
                <td>a cell.</td>
            </tr>
            <tr>
                <td></td>
                <td></td>
                <td>empty cells</td>
            </tr>
            </table>
            <p>...end</p>
        """,
                                  #            debug = True
                                  )

    def test_html_macro_unknown_nodes(self):
        """
        use the <<html>> macro to mask unknown tags.
        Note:
            All cross compare tests use html2creole.HTML_MACRO_UNKNOWN_NODES
        """
        self.cross_compare_creole("""
            111 <<html>><x><</html>>foo<<html>></x><</html>> 222
            333<<html>><x foo1="bar1"><</html>>foobar<<html>></x><</html>>444

            555<<html>><x /><</html>>666
        """, """
            <p>111 <x>foo</x> 222<br />
            333<x foo1="bar1">foobar</x>444</p>

            <p>555<x />666</p>
        """,
                                  # use macro in creole2html emitter:
                                  macros=example_macros,
                                  # escape unknown tags with <<html>> in html2creole emitter:
                                  unknown_emit=use_html_macro,
                                  )

    def test_entities(self):
        self.cross_compare_creole("""
            less-than sign: <
            greater-than sign: >
        """, """
            <p>less-than sign: &lt;<br />
            greater-than sign: &gt;</p>
        """)

#    def test_macro_html1(self):
#        self.cross_compare_creole(r"""
#            <<a_not_existing_macro>>
#
#            <<code>>
#            some code
#            <</code>>
#
#            a macro:
#            <<code>>
#            <<code>>
#            the sourcecode
#            <</code>>
#        """, r"""
#            <p>[Error: Macro 'a_not_existing_macro' doesn't exist]</p>
#            <fieldset class="pygments_code">
#            <legend class="pygments_code"><small title="no lexer matching the text found">unknown type</small></legend>
#            <pre><code>some code</code></pre>
#            </fieldset>
#            <p>a macro:</p>
#            <fieldset class="pygments_code">
#            <legend class="pygments_code"><small title="no lexer matching the text found">unknown type</small></legend>
#            <pre><code>&lt;&lt;code&gt;&gt;
#            the sourcecode</code></pre>
#            </fieldset>
#        """)


#    def test_macro_pygments_code(self):
#        self.cross_compare_creole(r"""
#            a macro:
#            <<code ext=.css>>
#            /* Stylesheet */
#            form * {
#              vertical-align:middle;
#            }
#            <</code>>
#            the end
#        """, """
#            <p>a macro:</p>
#            <fieldset class="pygments_code">
#            <legend class="pygments_code">CSS</legend><table class="pygmentstable"><tr><td class="linenos"><pre>1
#            2
#            3
#            4</pre></td><td class="code"><div class="pygments"><pre><span class="c">/* Stylesheet */</span>
#            <span class="nt">form</span> <span class="o">*</span> <span class="p">{</span>
#              <span class="k">vertical-align</span><span class="o">:</span><span class="k">middle</span><span class="p">;</span>
#            <span class="p">}</span>
#            </pre></div>
#            </td></tr></table></fieldset>
#            <p>the end</p>
#        """)


if __name__ == '__main__':
    unittest.main()
