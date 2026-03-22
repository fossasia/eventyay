"""
    creole2html unittest
    ~~~~~~~~~~~~~~~~~~~~

    Here are only some tests witch doesn't work in the cross compare tests.

    Info: There exist some situations with different whitespace handling
        between creol2html and html2creole.

    Test the creole markup.

    :copyleft: 2008-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import sys
import unittest
from io import StringIO

from creole import creole2html
from creole.shared import example_macros
from creole.shared.utils import dict2string, string2dict
from creole.tests import test_macros
from creole.tests.utils.base_unittest import BaseCreoleTest


try:
    import pygments  # noqa flake8
    PYGMENTS = True
except ImportError:
    PYGMENTS = False


class TestCreole2html(BaseCreoleTest):
    """
    Tests around creole2html API and macro function.
    """

    def setUp(self):
        # For fallback tests
        example_macros.PYGMENTS = PYGMENTS

    def test_stderr(self):
        """
        Test if the traceback information send to a stderr handler.
        """
        my_stderr = StringIO()
        creole2html(
            markup_string="<<notexist1>><<notexist2>><</notexist2>>",
            emitter_kwargs={
                "verbose": 2,
                "stderr": my_stderr,
            }
        )
        error_msg = my_stderr.getvalue()

        # Note:
        # The error message change if macros are a dict or are a object!

        # Check if we get a traceback information into our stderr handler
        must_have = (
            "Traceback", "'notexist1'", "'notexist2'",
        )
        for part in must_have:
            tb_lines = [" -" * 40]
            tb_lines += error_msg.splitlines()
            tb_lines += [" -" * 40]
            tb = "\n".join(f" >>> {line}" for line in tb_lines)
            msg = f"{part!r} not found in:\n{tb}"
            # TODO: use assertIn if python 2.6 will be not support anymore.
            if part not in error_msg:
                raise self.failureException(msg)

    def test_example_macros1(self):
        """
        Test the default "html" macro, found in ./creole/default_macros.py
        """
        html = creole2html(
            markup_string="<<html>><p>foo</p><</html>><bar?>",
            emitter_kwargs={
                "verbose": 1,
                "macros": example_macros,
                "stderr": sys.stderr,
            }
        )
        self.assertEqual(html, '<p>foo</p>\n<p>&lt;bar?&gt;</p>')

    def test_example_macros2(self):
        html = creole2html(
            markup_string="<<html>>{{{&lt;nocode&gt;}}}<</html>>",
            emitter_kwargs={
                "verbose": 1,
                "macros": example_macros,
                "stderr": sys.stderr,
            }
        )
        self.assertEqual(html, '{{{&lt;nocode&gt;}}}')

    def test_example_macros3(self):
        html = creole2html(
            markup_string="<<html>>1<</html>><<html>>2<</html>>",
            emitter_kwargs={
                "verbose": 1,
                "macros": example_macros,
                "stderr": sys.stderr,
            }
        )
        self.assertEqual(html, '1\n2')

    def test_macro_dict(self):
        """
        simple test for the "macro API"
        """
        def test(text, foo, bar):
            return "|".join([foo, bar, text])

        html = creole2html(
            markup_string="<<test bar='b' foo='a'>>c<</test>>",
            emitter_kwargs={
                "verbose": 1,
                "macros": {"test": test},
                "stderr": sys.stderr,
            }
        )
        self.assertEqual(html, 'a|b|c')

    def test_macro_callable(self):
        """
        simple test for the "macro API"
        """
        def testmacro():
            pass

        self.assertRaises(TypeError,
                          creole2html,
                          markup_string="<<test no=1 arg2='foo'>>bar<</test>>",
                          emitter_kwargs={
                              "verbose": 1,
                              "macros": testmacro,
                              "stderr": sys.stderr,
                          }
                          )

    def test_macro_wrong_arguments_with_error_report(self):
        """
        simple test for the "macro API"
        """
        def test(text, foo):
            pass
        my_stderr = StringIO()

        html = creole2html(
            markup_string="<<test bar='foo'>>c<</test>>",
            emitter_kwargs={
                "verbose": 2,
                "macros": {"test": test},
                "stderr": my_stderr,
            }
        )
        self.assertEqual(html,
                         "[Error: Macro 'test' error: test() got an unexpected keyword argument 'bar']"
                         )
        error_msg = my_stderr.getvalue()

        # Check traceback information into our stderr handler
        must_have = (
            "TypeError: test() got an unexpected keyword argument 'bar'",
            "sourceline: 'def test(text, foo):' from",
            "tests/test_creole2html.py",
        )
        for part in must_have:
            self.assertIn(part, error_msg)

    def test_macro_wrong_arguments_quite(self):
        """
        simple test for the "macro API"
        """
        def test(text, foo):
            pass
        my_stderr = StringIO()

        html = creole2html(
            markup_string="<<test bar='foo'>>c<</test>>",
            emitter_kwargs={
                "verbose": 1,
                "macros": {"test": test},
                "stderr": my_stderr,
            }
        )
        self.assertEqual(html,
                         "[Error: Macro 'test' error: test() got an unexpected keyword argument 'bar']"
                         )
        error_msg = my_stderr.getvalue()
        self.assertEqual(error_msg, "")

    @unittest.skipIf(not PYGMENTS, "Pygments not installed")
    def test_code_macro(self):
        # due to https://bitbucket.org/birkenfeld/pygments-main/issues/1254/empty-at-the-begining-of-the-highlight
        # an empty <span></span> is now part of pygments output
        self.assert_creole2html(r"""
            Here a simple code macro test:
            <<code ext=".py">>
            for i in xrange(10):
                print('hello world')
            <</code>>
            """, """
            <p>Here a simple code macro test:</p>
            <div class="pygments"><pre><span></span><span class="k">for</span> <span class="n">i</span> <span class="ow">in</span> <span class="n">xrange</span><span class="p">(</span><span class="mi">10</span><span class="p">):</span><br />
                <span class="nb">print</span><span class="p">(</span><span class="s1">&#39;hello world&#39;</span><span class="p">)</span><br />
            </pre></div><br />
            """,
                                macros={'code': example_macros.code}
                                )

    def test_code_macro_fallback(self):
        # force to use fallback. Will be reset in self.setUp()
        example_macros.PYGMENTS = False

        self.assert_creole2html(
            r"""
            Here a simple code macro test:
            <<code ext=".py">>
            for i in xrange(10):
                print('hello world')
            <</code>>
            """, """
            <p>Here a simple code macro test:</p>
            <pre>for i in xrange(10):
                print('hello world')</pre>
            """,
            macros={'code': example_macros.code}
        )

    def test_code_macro_fallback_escape(self):
        # force to use fallback. Will be reset in self.setUp()
        example_macros.PYGMENTS = False

        self.assert_creole2html(
            r"""
            <<code ext=".py">>
            print('This >>should<< be escaped!')
            <</code>>
            """, """
            <pre>print('This &gt;&gt;should&lt;&lt; be escaped!')</pre>
            """,
            macros={'code': example_macros.code}
        )


class TestCreole2htmlMarkup(BaseCreoleTest):

    def test_creole_basic(self):
        out_string = creole2html("a text line.")
        self.assertEqual(out_string, "<p>a text line.</p>")

    def test_lineendings(self):
        """ Test all existing lineending version """
        out_string = creole2html("first\nsecond")
        self.assertEqual(out_string, "<p>first<br />\nsecond</p>")

        out_string = creole2html("first\rsecond")
        self.assertEqual(out_string, "<p>first<br />\nsecond</p>")

        out_string = creole2html("first\r\nsecond")
        self.assertEqual(out_string, "<p>first<br />\nsecond</p>")

    # --------------------------------------------------------------------------

    def test_creole_linebreak(self):
        self.assert_creole2html(r"""
            Force\\linebreak
        """, """
            <p>Force<br />
            linebreak</p>
        """)

    def test_html_lines(self):
        self.assert_creole2html(r"""
            This is a normal Text block witch would
            escape html chars like < and > ;)

            So you can't insert <html> directly.

            <p>This escaped, too.</p>
        """, """
            <p>This is a normal Text block witch would<br />
            escape html chars like &lt; and &gt; ;)</p>

            <p>So you can't insert &lt;html&gt; directly.</p>

            <p>&lt;p&gt;This escaped, too.&lt;/p&gt;</p>
        """)

    def test_escape_char(self):
        self.assert_creole2html(r"""
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

    def test_cross_paragraphs(self):
        self.assert_creole2html(r"""
            Bold and italics should //not be...

            ...able// to **cross

            paragraphs.**
        """, """
            <p>Bold and italics should //not be...</p>

            <p>...able// to **cross</p>

            <p>paragraphs.**</p>
        """)

    def test_list_special(self):
        """
        optional whitespace before the list
        """
        self.assert_creole2html(r"""
            * Item 1
            ** Item 1.1
             ** Item 1.2
                ** Item 1.3
                    * Item2

                # one
              ## two
        """, """
        <ul>
            <li>Item 1
            <ul>
                <li>Item 1.1</li>
                <li>Item 1.2</li>
                <li>Item 1.3</li>
            </ul></li>
            <li>Item2</li>
        </ul>
        <ol>
            <li>one
            <ol>
                <li>two</li>
            </ol></li>
        </ol>
        """)

    def test_macro_basic(self):
        """
        Test the three different macro types with a "unittest macro"
        """
        self.assert_creole2html(r"""
            There exist three different macro types:
            A <<unittest_macro1 args="foo1">>bar1<</unittest_macro1>> in a line...
            ...a single <<unittest_macro1 foo="bar">> tag,
            or: <<unittest_macro1 a=1 b=2 />> closed...

            a macro block:
            <<unittest_macro2 char="|">>
            the
            text
            <</unittest_macro2>>
            the end
        """, r"""
            <p>There exist three different macro types:<br />
            A [test macro1 - kwargs: args="foo1",text="bar1"] in a line...<br />
            ...a single [test macro1 - kwargs: foo="bar",text=null] tag,<br />
            or: [test macro1 - kwargs: a=1,b=2,text=null] closed...</p>

            <p>a macro block:</p>
            the|text
            <p>the end</p>
        """,
                                macros=test_macros,
                                )

    def test_macro_html1(self):
        self.assert_creole2html(r"""
                html macro:
                <<html>>
                <p><<this is broken 'html', but it will be pass throu>></p>
                <</html>>

                inline: <<html>>&#x7B;...&#x7D;<</html>> code
            """, r"""
                <p>html macro:</p>
                <p><<this is broken 'html', but it will be pass throu>></p>

                <p>inline: &#x7B;...&#x7D; code</p>
            """,
                                macros=example_macros,
                                )

    def test_macro_not_exist1(self):
        """
        not existing macro with creole2html.HtmlEmitter(verbose=1):
        A error message should be insertet into the generated code

        Two tests: with verbose=1 and verbose=2, witch write a Traceback
        information to a given "stderr"
        """
        source_string = r"""
            macro block:
            <<notexists>>
            foo bar
            <</notexists>>

            inline macro:
            <<notexisttoo foo="bar">>
        """
        should_string = r"""
            <p>macro block:</p>
            [Error: Macro 'notexists' doesn't exist]

            <p>inline macro:<br />
            [Error: Macro 'notexisttoo' doesn't exist]
            </p>
        """

        self.assert_creole2html(source_string, should_string, verbose=1)

        # ----------------------------------------------------------------------
        # Test with verbose=2 ans a StringIO stderr handler

    def test_wrong_macro_syntax(self):
        self.assert_creole2html(r"""
                wrong macro line:
                <<summary>Some funky page summary.<</summary>>
            """, r"""
                <p>wrong macro line:<br />
                [Error: Wrong macro arguments: ">Some funky page summary.<</summary" for macro 'summary' (maybe wrong macro tag syntax?)]
                </p>
            """,  # verbose=True
                                )

    def test_macro_not_exist2(self):
        """
        not existing macro with creole2html.HtmlEmitter(verbose=0):

        No error messages should be inserted.
        """
        self.assert_creole2html(r"""
            macro block:
            <<notexists>>
            foo bar
            <</notexists>>

            inline macro:
            <<notexisttoo foo="bar">>
        """, r"""
            <p>macro block:</p>

            <p>inline macro:<br />
            </p>
        """, verbose=False
                                )

    def test_toc_simple(self):
        """
        Simple test to check the table of content is correctly generated.
        """
        self.assert_creole2html(r"""
            <<toc>>
            = Headline
        """, """
            <ul>
                <li><a href="#Headline">Headline</a></li>
            </ul>
            <a name="Headline"><h1>Headline</h1></a>
        """)

    def test_toc_more_headlines(self):
        self.assert_creole2html(r"""
            Between text and toc must be a newline.

            <<toc>>
            = Headline 1
            == Sub-Headline 1.1
            == Sub-Headline 1.2
            = Headline 2
            == Sub-Headline 2.1
            == Sub-Headline 2.2
        """, """
            <p>Between text and toc must be a newline.</p>

            <ul>
                <li><a href="#Headline 1">Headline 1</a></li>
                <ul>
                    <li><a href="#Sub-Headline 1.1">Sub-Headline 1.1</a></li>
                    <li><a href="#Sub-Headline 1.2">Sub-Headline 1.2</a></li>
                </ul>
                <li><a href="#Headline 2">Headline 2</a></li>
                <ul>
                    <li><a href="#Sub-Headline 2.1">Sub-Headline 2.1</a></li>
                    <li><a href="#Sub-Headline 2.2">Sub-Headline 2.2</a></li>
                </ul>
            </ul>
            <a name="Headline 1"><h1>Headline 1</h1></a>
            <a name="Sub-Headline 1.1"><h2>Sub-Headline 1.1</h2></a>
            <a name="Sub-Headline 1.2"><h2>Sub-Headline 1.2</h2></a>
            <a name="Headline 2"><h1>Headline 2</h1></a>
            <a name="Sub-Headline 2.1"><h2>Sub-Headline 2.1</h2></a>
            <a name="Sub-Headline 2.2"><h2>Sub-Headline 2.2</h2></a>
        """)

    def test_toc_chaotic_headlines(self):
        self.assert_creole2html(r"""
            <<toc>>
            = level 1
            === level 3
            == level 2
            ==== level 4
            = level 1
        """, """
            <ul>
                <li><a href="#level 1">level 1</a></li>
                <ul>
                    <ul>
                        <li><a href="#level 3">level 3</a></li>
                    </ul>
                    <li><a href="#level 2">level 2</a></li>
                    <ul>
                        <ul>
                            <li><a href="#level 4">level 4</a></li>
                        </ul>
                    </ul>
                </ul>
                <li><a href="#level 1">level 1</a></li>
            </ul>
            <a name="level 1"><h1>level 1</h1></a>
            <a name="level 3"><h3>level 3</h3></a>
            <a name="level 2"><h2>level 2</h2></a>
            <a name="level 4"><h4>level 4</h4></a>
            <a name="level 1"><h1>level 1</h1></a>
        """)

    def test_toc_depth_1(self):
        self.assert_creole2html(r"""
            <<toc depth=1>>
            = Headline 1
            == Sub-Headline 1.1
            === Sub-Sub-Headline 1.1.1
            === Sub-Sub-Headline 1.1.2
            == Sub-Headline 1.2
            = Headline 2
            == Sub-Headline 2.1
            == Sub-Headline 2.2
            === Sub-Sub-Headline 2.2.1
        """, """
            <ul>
                <li><a href="#Headline 1">Headline 1</a></li>
                <li><a href="#Headline 2">Headline 2</a></li>
            </ul>
            <a name="Headline 1"><h1>Headline 1</h1></a>
            <a name="Sub-Headline 1.1"><h2>Sub-Headline 1.1</h2></a>
            <a name="Sub-Sub-Headline 1.1.1"><h3>Sub-Sub-Headline 1.1.1</h3></a>
            <a name="Sub-Sub-Headline 1.1.2"><h3>Sub-Sub-Headline 1.1.2</h3></a>
            <a name="Sub-Headline 1.2"><h2>Sub-Headline 1.2</h2></a>
            <a name="Headline 2"><h1>Headline 2</h1></a>
            <a name="Sub-Headline 2.1"><h2>Sub-Headline 2.1</h2></a>
            <a name="Sub-Headline 2.2"><h2>Sub-Headline 2.2</h2></a>
            <a name="Sub-Sub-Headline 2.2.1"><h3>Sub-Sub-Headline 2.2.1</h3></a>
        """)

    def test_toc_depth_2(self):
        self.assert_creole2html(r"""
            <<toc depth=2>>
            = Headline 1
            == Sub-Headline 1.1
            === Sub-Sub-Headline 1.1.1
            === Sub-Sub-Headline 1.1.2
            == Sub-Headline 1.2
            = Headline 2
            == Sub-Headline 2.1
            == Sub-Headline 2.2
            === Sub-Sub-Headline 2.2.1
        """, """
            <ul>
                <li><a href="#Headline 1">Headline 1</a></li>
                <ul>
                    <li><a href="#Sub-Headline 1.1">Sub-Headline 1.1</a></li>
                    <li><a href="#Sub-Headline 1.2">Sub-Headline 1.2</a></li>
                </ul>
                <li><a href="#Headline 2">Headline 2</a></li>
                <ul>
                    <li><a href="#Sub-Headline 2.1">Sub-Headline 2.1</a></li>
                    <li><a href="#Sub-Headline 2.2">Sub-Headline 2.2</a></li>
                </ul>
            </ul>
            <a name="Headline 1"><h1>Headline 1</h1></a>
            <a name="Sub-Headline 1.1"><h2>Sub-Headline 1.1</h2></a>
            <a name="Sub-Sub-Headline 1.1.1"><h3>Sub-Sub-Headline 1.1.1</h3></a>
            <a name="Sub-Sub-Headline 1.1.2"><h3>Sub-Sub-Headline 1.1.2</h3></a>
            <a name="Sub-Headline 1.2"><h2>Sub-Headline 1.2</h2></a>
            <a name="Headline 2"><h1>Headline 2</h1></a>
            <a name="Sub-Headline 2.1"><h2>Sub-Headline 2.1</h2></a>
            <a name="Sub-Headline 2.2"><h2>Sub-Headline 2.2</h2></a>
            <a name="Sub-Sub-Headline 2.2.1"><h3>Sub-Sub-Headline 2.2.1</h3></a>
        """)

    def test_toc_depth_3(self):
        self.assert_creole2html(r"""
            <<toc depth=3>>
            = Headline 1
            == Sub-Headline 1.1
            === Sub-Sub-Headline 1.1.1
            === Sub-Sub-Headline 1.1.2
            == Sub-Headline 1.2
            = Headline 2
            == Sub-Headline 2.1
            == Sub-Headline 2.2
            === Sub-Sub-Headline 2.2.1
        """, """
            <ul>
                <li><a href="#Headline 1">Headline 1</a></li>
                <ul>
                    <li><a href="#Sub-Headline 1.1">Sub-Headline 1.1</a></li>
                    <ul>
                        <li><a href="#Sub-Sub-Headline 1.1.1">Sub-Sub-Headline 1.1.1</a></li>
                        <li><a href="#Sub-Sub-Headline 1.1.2">Sub-Sub-Headline 1.1.2</a></li>
                    </ul>
                    <li><a href="#Sub-Headline 1.2">Sub-Headline 1.2</a></li>
                </ul>
                <li><a href="#Headline 2">Headline 2</a></li>
                <ul>
                    <li><a href="#Sub-Headline 2.1">Sub-Headline 2.1</a></li>
                    <li><a href="#Sub-Headline 2.2">Sub-Headline 2.2</a></li>
                    <ul>
                        <li><a href="#Sub-Sub-Headline 2.2.1">Sub-Sub-Headline 2.2.1</a></li>
                    </ul>
                </ul>
            </ul>
            <a name="Headline 1"><h1>Headline 1</h1></a>
            <a name="Sub-Headline 1.1"><h2>Sub-Headline 1.1</h2></a>
            <a name="Sub-Sub-Headline 1.1.1"><h3>Sub-Sub-Headline 1.1.1</h3></a>
            <a name="Sub-Sub-Headline 1.1.2"><h3>Sub-Sub-Headline 1.1.2</h3></a>
            <a name="Sub-Headline 1.2"><h2>Sub-Headline 1.2</h2></a>
            <a name="Headline 2"><h1>Headline 2</h1></a>
            <a name="Sub-Headline 2.1"><h2>Sub-Headline 2.1</h2></a>
            <a name="Sub-Headline 2.2"><h2>Sub-Headline 2.2</h2></a>
            <a name="Sub-Sub-Headline 2.2.1"><h3>Sub-Sub-Headline 2.2.1</h3></a>
        """)

    def test_toc_with_no_toc(self):
        self.assert_creole2html(r"""
            <<toc>>
            = This is the Headline
            Use {{{<<toc>>}}} to insert a table of contents.
        """, """
            <ul>
                <li><a href="#This is the Headline">This is the Headline</a></li>
            </ul>
            <a name="This is the Headline"><h1>This is the Headline</h1></a>
            <p>Use <tt>&lt;&lt;toc&gt;&gt;</tt> to insert a table of contents.</p>
        """)

    def test_toc_more_then_one_toc(self):
        self.assert_creole2html(r"""
            Not here:
            {{{
            print("<<toc>>")
            }}}

            and onle the first:

            <<toc>>

            <<toc>>
            <<toc>>
            = Headline
            == Sub-Headline
        """, """
            <p>Not here:</p>
            <pre>
            print("&lt;&lt;toc&gt;&gt;")
            </pre>

            <p>and onle the first:</p>

            <ul>
                <li><a href="#Headline">Headline</a></li>
                <ul>
                    <li><a href="#Sub-Headline">Sub-Headline</a></li>
                </ul>
            </ul>

            <p>&lt;&lt;toc&gt;&gt;<br />
            &lt;&lt;toc&gt;&gt;</p>
            <a name="Headline"><h1>Headline</h1></a>
            <a name="Sub-Headline"><h2>Sub-Headline</h2></a>
        """)

    def test_toc_headline_before_toc(self):
        self.assert_creole2html(r"""
            = headline
            == sub headline

            <<toc>>

            ok?
        """, """
            <a name="headline"><h1>headline</h1></a>
            <a name="sub headline"><h2>sub headline</h2></a>

            <ul>
                <li><a href="#headline">headline</a></li>
                <ul>
                    <li><a href="#sub headline">sub headline</a></li>
                </ul>
            </ul>

            <p>ok?</p>
        """)

    def test_image(self):
        """ test image tag with different picture text """
        self.assert_creole2html(r"""
            {{foobar1.jpg}}
            {{/path1/path2/foobar2.jpg}}
            {{/path1/path2/foobar3.jpg|foobar3.jpg}}
        """, """
            <p><img src="foobar1.jpg" title="foobar1.jpg" alt="foobar1.jpg" /><br />
            <img src="/path1/path2/foobar2.jpg" title="/path1/path2/foobar2.jpg" alt="/path1/path2/foobar2.jpg" /><br />
            <img src="/path1/path2/foobar3.jpg" title="foobar3.jpg" alt="foobar3.jpg" /></p>
        """)

    def test_image_with_size(self):
        """ test image tag with size dimention (good and bad) """
        self.assert_creole2html(r"""
            {{/path1/path2/foobar3.jpg|foo|160x90}}
            {{/path1/path2/foobar3.jpg|foo| 160 x 90 }}
            {{/path1/path2/foobar3.jpg|foo|160}}
            {{/path1/path2/foobar3.jpg||160x90}}
            {{/path1/path2/foobar3.jpg|foo|}}
        """, """
            <p><img src="/path1/path2/foobar3.jpg" title="foo" alt="foo" width="160" height="90" /><br />
            <img src="/path1/path2/foobar3.jpg" title="foo" alt="foo" width="160" height="90" /><br />
            <img src="/path1/path2/foobar3.jpg" title="foo|160" alt="foo|160" /><br />
            <img src="/path1/path2/foobar3.jpg" title="/path1/path2/foobar3.jpg" alt="/path1/path2/foobar3.jpg" width="160" height="90" /><br />
            <img src="/path1/path2/foobar3.jpg" title="foo|" alt="foo|" /></p>
        """)

    def test_image_with_size_strict(self):
        """ test image tag with size dimention (good and bad) """
        self.assert_creole2html(r"""
            {{/path1/path2/foobar3.jpg|foo|160x90}}
            {{/path1/path2/foobar3.jpg|foo|160}}
        """, """
            <p><img src="/path1/path2/foobar3.jpg" title="foo|160x90" alt="foo|160x90" /><br />
            <img src="/path1/path2/foobar3.jpg" title="foo|160" alt="foo|160" /></p>
        """, strict=True)

    def test_image_unknown_extension(self):
        self.assert_creole2html(r"""
            # {{/path/to/image.ext|image ext}} one
            # {{/no/extension|no extension}} two
            # {{/image.xyz}} tree
        """, """
            <ol>
                <li><img src="/path/to/image.ext" title="image ext" alt="image ext" /> one</li>
                <li><img src="/no/extension" title="no extension" alt="no extension" /> two</li>
                <li><img src="/image.xyz" title="/image.xyz" alt="/image.xyz" /> tree</li>
            </ol>
        """)

    def test_links(self):
        self.assert_creole2html(r"""
            [[/foobar/Creole_(Markup)]]
            [[http://de.wikipedia.org/wiki/Creole_(Markup)|Creole@wikipedia]]
        """, """
            <p><a href="/foobar/Creole_(Markup)">/foobar/Creole_(Markup)</a><br />
            <a href="http://de.wikipedia.org/wiki/Creole_(Markup)">Creole@wikipedia</a></p>
        """)

    def test_standalone_hyperlink(self):
        self.assert_creole2html(r"""
                a link to the http://www.pylucid.org page.
            """, """
                <p>a link to the <a href="http://www.pylucid.org">http://www.pylucid.org</a> page.</p>
            """
                                )

    def test_wiki_style_line_breaks1(self):
        html = creole2html(
            markup_string=self._prepare_text("""
                wiki style
                linebreaks

                ...and not blog styled.
            """),
            blog_line_breaks=False,
            debug=True, verbose=True
        )
        self.assertEqual(html, self._prepare_text("""
            <p>wiki style linebreaks</p>

            <p>...and not blog styled.</p>
        """))

    def test_wiki_style_line_breaks2(self):
        html = creole2html(
            markup_string=self._prepare_text("""
                **one**
                //two//

                * one
                * two
            """),
            blog_line_breaks=False,
            debug=True, verbose=True
        )
        self.assertEqual(html, self._prepare_text("""
            <p><strong>one</strong> <i>two</i></p>

            <ul>
            \t<li>one</li>
            \t<li>two</li>
            </ul>
        """))

    def test_wiki_style_line_breaks3(self):
        html = creole2html(
            markup_string=self._prepare_text("""
                with blog line breaks, every line break would be convertet into<br />
                with wiki style not.

                This is the first line,\\\\and this is the second.

                new line
                block 1

                new line
                block 2

                end
            """),
            blog_line_breaks=False,
        )
        self.assertEqual(html, self._prepare_text("""
            <p>with blog line breaks, every line break would be convertet into&lt;br /&gt; with wiki style not.</p>

            <p>This is the first line,<br />
            and this is the second.</p>

            <p>new line block 1</p>

            <p>new line block 2</p>

            <p>end</p>
        """))

    def test_headline_spaces(self):
        """
        https://code.google.com/p/python-creole/issues/detail?id=15
        """
        html = creole2html(markup_string="== Headline1 == \n== Headline2== ")
        self.assertEqual(html, self._prepare_text("""
            <h2>Headline1</h2>
            <h2>Headline2</h2>
        """))

    def test_tt(self):
        self.assert_creole2html(r"""
            inline {{{<escaped>}}} and {{{ **not strong** }}}...
            ...and ##**strong** Teletyper## ;)
        """, """
            <p>inline <tt>&lt;escaped&gt;</tt> and <tt> **not strong** </tt>...<br />
            ...and <tt><strong>strong</strong> Teletyper</tt> ;)</p>
        """)

    def test_protocol_in_brackets(self):
        self.assert_creole2html(r"""
            My Server ([[ftp://foo/bar]]) is ok.
        """, """
            <p>My Server (<a href="ftp://foo/bar">ftp://foo/bar</a>) is ok.</p>
        """)
        self.assert_creole2html(r"""
            My Server (ftp://foo/bar) is ok.
        """, """
            <p>My Server (ftp://foo/bar) is ok.</p>
        """)

    def test_protocol_with_brackets(self):
        self.assert_creole2html(r"""
            A http://en.wikipedia.org/wiki/Uri_(Island) link.
        """, """
            <p>A <a href="http://en.wikipedia.org/wiki/Uri_(Island)">http://en.wikipedia.org/wiki/Uri_(Island)</a> link.</p>
        """)

    def test_wrong_protocol(self):
        self.assert_creole2html(r"""
            ~ftp://ok
        """, """
            <p>ftp://ok</p>
        """)
        self.assert_creole2html(r"""
            ftp:
        """, """
            <p>ftp:</p>
        """)
        self.assert_creole2html(r"""
            ftp:/
        """, """
            <p>ftp:/</p>
        """)
        self.assert_creole2html(r"""
            missing space.ftp://ok
        """, """
            <p>missing space.ftp://ok</p>
        """)


class TestStr2Dict(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            string2dict('key1="value1" key2="value2"'),
            {'key2': 'value2', 'key1': 'value1'}
        )

    def test_bool(self):
        self.assertEqual(
            string2dict('unicode=True'),
            {'unicode': True}
        )

    def test_mixed1(self):
        self.assertEqual(
            string2dict('A="B" C=1 D=1.1 E=True F=False G=None'),
            {'A': 'B', 'C': 1, 'E': True, 'D': '1.1', 'G': None, 'F': False}
        )

    def test_mixed2(self):
        self.assertEqual(
            string2dict('''key1="'1'" key2='"2"' key3="""'3'""" '''),
            {'key3': 3, 'key2': 2, 'key1': 1}
        )


class TestDict2String(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            dict2string({'key': 'value'}),
            'key="value"'
        )

    def test_basic2(self):
        self.assertEqual(
            dict2string({'foo': "bar", "no": 123}),
            'foo="bar" no=123'
        )

    def test_basic3(self):
        self.assertEqual(
            dict2string({"foo": 'bar', "no": "ABC"}),
            'foo="bar" no="ABC"'
        )


if __name__ == '__main__':
    unittest.main(
        verbosity=2
    )
