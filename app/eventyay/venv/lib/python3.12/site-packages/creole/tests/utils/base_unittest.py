"""
    unitest base class
    ~~~~~~~~~~~~~~~~~~

    Basic unittest class for all python-creole tests.

    :copyleft: 2008-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import re

import textile

from creole import creole2html, html2creole, html2rest, html2textile
from creole.rest_tools.clean_writer import rest2html
from creole.tests.utils.utils import MarkupTest


tabs2spaces_re = re.compile(r"^(\t*)(.*?)$", re.M)


def tabs2spaces(html):
    """ form reformating textile html code
    >>> tabs2spaces("\\t<p>one<br />\\n\\t\\ttwo<br />\\n\\t\\t\\ttree</p>")
    '<p>one<br />\\n  two<br />\\n    tree</p>'
    """
    def reformat_tabs(match):
        tabs = match.group(1)
        text = match.group(2)

        indent = len(tabs) - 1
        if indent < 0:
            indent = 0

#        print(len(tabs), indent, repr(tabs), text)
        return "  " * indent + text
    return tabs2spaces_re.sub(reformat_tabs, html)


def strip_html_lines(html, strip_lines=False):
    """
    >>> strip_html_lines("\t<p>foo   \\n\\n\t\t  bar</p>", strip_lines=True)
    '<p>foo\\nbar</p>'
    """
    html = "\n".join(
        [line.strip(" \t") for line in html.splitlines() if line]
    )
    return html


class BaseCreoleTest(MarkupTest):
    """
    Basic unittest class for all python-creole unittest classes.
    """

    def _debug_text(self, msg, raw_text):
        text = raw_text.replace(" ", ".")
        text = text.replace("\n", "\\n\n")
        text = text.replace("\t", "\\t")

        print()
        print("_" * 79)
        print(f" Debug Text: {msg}:")
        print(text)
        print("-" * 79)

    def assert_creole2html(
        self, raw_creole, raw_html,
        strip_lines=False, debug=True,
        parser_kwargs={}, emitter_kwargs={},
        block_rules=None, blog_line_breaks=True, macros=None, verbose=True, stderr=None,
        strict=False,
    ):
        """
        compare the generated html code from the markup string >creole_string<
        with the >html_string< reference.
        """
        self.assertNotEqual(raw_creole, raw_html)
        self.assertEqual(parser_kwargs, {}, "parser_kwargs is deprecated!")
        self.assertEqual(emitter_kwargs, {}, "parser_kwargs is deprecated!")

        # prepare whitespace on test strings
        markup_string = self._prepare_text(raw_creole)
        assert isinstance(markup_string, str)

        html_string = self._prepare_text(raw_html)
        assert isinstance(html_string, str)
        if strip_lines:
            html_string = strip_html_lines(html_string, strip_lines)
        self._debug_text("assert_creole2html() html_string reference", html_string)

        # convert creole markup into html code
        out_string = creole2html(
            markup_string, debug=debug,
            block_rules=block_rules, blog_line_breaks=blog_line_breaks,
            macros=macros, verbose=verbose, stderr=stderr,
            strict=strict,
        )
        self._debug_text("assert_creole2html() creole2html output", out_string)

        if strip_lines:
            out_string = strip_html_lines(out_string, strip_lines)
        else:
            out_string = out_string.replace("\t", "    ")

        # compare
        self.assertEqual(out_string, html_string, msg="creole2html")

    def assert_html2creole2(self, creole, html,
                            debug=True,
                            unknown_emit=None,
                            strict=False,
                            ):
        # convert html code into creole markup
        out_string = html2creole(
            html, debug, unknown_emit=unknown_emit, strict=strict
        )
        self._debug_text("assert_html2creole() html2creole", out_string)

        # compare
        self.assertEqual(out_string, creole, msg="html2creole")

    def assert_html2creole(self, raw_creole, raw_html,
                           strip_lines=False, debug=True,
                           # OLD API:
                           parser_kwargs={}, emitter_kwargs={},
                           # html2creole:
                           unknown_emit=None,
                           strict=False,
                           ):
        """
        Compare the genereted markup from the given >raw_html< html code, with
        the given >creole_string< reference string.
        """
        self.assertEqual(parser_kwargs, {}, "parser_kwargs is deprecated!")
        self.assertEqual(emitter_kwargs, {}, "parser_kwargs is deprecated!")
#        assert isinstance(raw_html, str)
#        creole_string = unicode(creole_string, encoding="utf8")
#        raw_html = unicode(raw_html, "utf8")

        self.assertNotEqual(raw_creole, raw_html)

        # prepare whitespace on test strings
        creole = self._prepare_text(raw_creole)
        assert isinstance(creole, str)
        if debug:
            self._debug_text("assert_creole2html() markup", creole)

        html = self._prepare_text(raw_html)
        assert isinstance(html, str)

        self.assert_html2creole2(creole, html, debug, unknown_emit, strict)

    def cross_compare_creole(self, creole_string, html_string,
                             strip_lines=False, debug=True,
                             # creole2html old API:
                             creole_parser_kwargs={}, html_emitter_kwargs={},
                             # html2creole old API:
                             html_parser_kwargs={}, creole_emitter_kwargs={},

                             # creole2html new API:
                             block_rules=None, blog_line_breaks=True, macros=None, stderr=None,
                             # html2creole:
                             unknown_emit=None
                             ):
        """
        Cross compare with:
            * creole2html
            * html2creole
        """
        self.assertEqual(creole_parser_kwargs, {}, "creole_parser_kwargs is deprecated!")
        self.assertEqual(html_emitter_kwargs, {}, "html_emitter_kwargs is deprecated!")
        self.assertEqual(html_parser_kwargs, {}, "html_parser_kwargs is deprecated!")
        self.assertEqual(creole_emitter_kwargs, {}, "creole_emitter_kwargs is deprecated!")

        assert isinstance(creole_string, str)
        assert isinstance(html_string, str)
        self.assertNotEqual(creole_string, html_string)

        self.assert_creole2html(
            raw_creole=creole_string, raw_html=html_string,
            strip_lines=strip_lines,
            block_rules=block_rules, blog_line_breaks=blog_line_breaks,
            macros=macros, stderr=stderr,
        )

        self.assert_html2creole(
            raw_creole=creole_string, raw_html=html_string, strip_lines=strip_lines,
            unknown_emit=unknown_emit,
        )

    def assert_html2textile(self, textile_string, html_string,
                            strip_lines=False, debug=False, parser_kwargs={}, emitter_kwargs={}):
        """
        Check html2textile
        """
        self.assertNotEqual(textile_string, html_string)

        textile_string = self._prepare_text(textile_string)
        html_string = self._prepare_text(html_string)

        if strip_lines:
            html_string = strip_html_lines(html_string, strip_lines)

        # compare html -> textile
        textile_string2 = html2textile(html_string, debug, parser_kwargs, emitter_kwargs)
        if debug:
            print("-" * 79)
            print(textile_string2)
            print("-" * 79)

        self.assertEqual(textile_string2, textile_string, msg="html2textile")

        return textile_string, html_string

    def cross_compare_textile(self, textile_string, html_string,
                              strip_lines=False, debug=False, parser_kwargs={}, emitter_kwargs={}):
        """
            Checks:
                * html2textile
                * textile2html
        """
#        assert isinstance(textile_string, str)
#        assert isinstance(html_string, str)
        self.assertNotEqual(textile_string, html_string)

        # compare html -> textile
        textile_string, html_string = self.assert_html2textile(
            textile_string, html_string,
            strip_lines, debug, parser_kwargs, emitter_kwargs
        )

        # compare textile -> html
        html = textile.textile(textile_string)
        html = html.replace("<br />", "<br />\n")
        html = tabs2spaces(html)
        if strip_lines:
            html = strip_html_lines(html, strip_lines)

        self.assertEqual(html_string, html, msg="textile2html")

    def assert_html2rest(self, rest_string, html_string,
                         strip_lines=False, debug=False, parser_kwargs={}, emitter_kwargs={}):
        """
        Check html to reStructuredText converter
        """
        self.assertNotEqual(rest_string, html_string)

        rest_string = self._prepare_text(rest_string)
        print("-" * 100)
        print(rest_string)
        html_string = self._prepare_text(html_string)
        if strip_lines:
            html_string = strip_html_lines(html_string, strip_lines)
        print("-" * 100)
        print(html_string)

        # compare html -> reStructuredText
        rest_string2 = html2rest(html_string, debug, parser_kwargs, emitter_kwargs)
        print("-" * 100)
        print(rest_string2)
        print("-" * 100)

        self.assertEqual(rest_string2, rest_string, msg="html2rest")

        return rest_string, html_string

    def assert_rest2html(self, rest_string, html_string,
                         strip_lines=False, debug=False, prepare_strings=True, **kwargs):

        # compare rest -> html
        if prepare_strings:
            rest_string = self._prepare_text(rest_string)
            html_string = self._prepare_text(html_string)

        html = rest2html(rest_string, **kwargs)

        if debug:
            print(rest_string)
            print(html_string)
            print(html)

        html = html.strip()
#        html = html.replace("<br />", "<br />\n")
#        html = tabs2spaces(html)
        if strip_lines:
            html = strip_html_lines(html, strip_lines)

        self.assertEqual(html, html_string, msg="rest2html")

    def cross_compare_rest(self, rest_string, html_string,
                           strip_lines=False, debug=False, parser_kwargs={}, emitter_kwargs={}):
        #        assert isinstance(textile_string, str)
        #        assert isinstance(html_string, str)
        self.assertNotEqual(rest_string, html_string)

        rest_string, html_string = self.assert_html2rest(
            rest_string, html_string,
            strip_lines, debug, parser_kwargs, emitter_kwargs
        )

        # compare rest -> html
        self.assert_rest2html(
            rest_string, html_string,
            strip_lines=strip_lines, debug=debug,
            prepare_strings=False,
        )

    def cross_compare(self,
                      html_string,
                      creole_string=None,
                      textile_string=None,
                      rest_string=None,
                      strip_lines=False, debug=False, parser_kwargs={}, emitter_kwargs={}):
        """
        Cross compare with:
            * creole2html
            * html2creole
            * html2textile
            * html2ReSt
        """
        if creole_string:
            self.cross_compare_creole(
                creole_string, html_string, strip_lines, debug, parser_kwargs, emitter_kwargs
            )

        if textile_string:
            self.cross_compare_textile(
                textile_string, html_string, strip_lines, debug, parser_kwargs, emitter_kwargs
            )

        if rest_string:
            self.cross_compare_rest(
                rest_string, html_string, strip_lines, debug, parser_kwargs, emitter_kwargs
            )


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
