"""
    python-creole
    ~~~~~~~~~~~~~

    :copyleft: 2008-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import re
import warnings
from html.parser import HTMLParser

from creole.html_tools.strip_html import strip_html
from creole.parser.html_parser_config import BLOCK_TAGS, IGNORE_TAGS
from creole.shared.document_tree import DebugList, DocNode


# ------------------------------------------------------------------------------

block_re = re.compile(r'''
    ^<pre> \s* $
    (?P<pre_block>
        (\n|.)*?
    )
    ^</pre> \s* $
    [\s\n]*
''', re.VERBOSE | re.UNICODE | re.MULTILINE)

inline_re = re.compile(r'''
    <pre>
    (?P<pre_inline>
        (\n|.)*?
    )
    </pre>
''', re.VERBOSE | re.UNICODE)


headline_tag_re = re.compile(r"h(\d)", re.UNICODE)

# ------------------------------------------------------------------------------


class HtmlParser(HTMLParser):
    """
    parse html code and create a document tree.

    >>> p = HtmlParser()
    >>> p.feed("<p>html <strong>code</strong></p>")
    <DocNode document: None>
    >>> p.debug()
    ________________________________________________________________________________
      document tree:
    ================================================================================
    p
        data: 'html '
        strong
            data: 'code'
    ********************************************************************************

    >>> p = HtmlParser()
    >>> p.feed("<p>html1 <script>var foo='<em>BAR</em>';</script> html2</p>")
    <DocNode document: None>
    >>> p.debug()
    ________________________________________________________________________________
      document tree:
    ================================================================================
    p
        data: 'html1 '
        script
            data: "var foo='<em>BAR</em>';"
        data: ' html2'
    ********************************************************************************
    """
    # placeholder html tag for pre cutout areas:
    _block_placeholder = "blockdata"
    _inline_placeholder = "inlinedata"

    def __init__(self, debug=False):
        super().__init__(convert_charrefs=False)

        self.debugging = debug
        if self.debugging:
            warnings.warn(
                message="Html2Creole debug is on! warn every data append."
            )
            self.result = DebugList(self)
        else:
            self.result = []

        self.blockdata = []

        self.root = DocNode("document", None)
        self.cur = self.root

        self.__list_level = 0

    def _pre_cut(self, data, type, placeholder):
        if self.debugging:
            print(f"append blockdata: {data!r}")
        assert isinstance(data, str), "blockdata is not unicode"
        self.blockdata.append(data)
        id = len(self.blockdata) - 1
        return f'<{placeholder} type="{type}" id="{id}" />'

    def _pre_pre_inline_cut(self, groups):
        return self._pre_cut(groups["pre_inline"], "pre", self._inline_placeholder)

    def _pre_pre_block_cut(self, groups):
        return self._pre_cut(groups["pre_block"], "pre", self._block_placeholder)

    def _pre_pass_block_cut(self, groups):
        content = groups["pass_block"].strip()
        return self._pre_cut(content, "pass", self._block_placeholder)

    _pre_pass_block_start_cut = _pre_pass_block_cut

    def _pre_cut_out(self, match):
        groups = match.groupdict()
        for name, text in groups.items():
            if text is not None:
                if self.debugging:
                    print(f"{name:>15}: {text!r} ({match.group(0)!r})")
                method = getattr(self, f'_pre_{name}_cut')
                return method(groups)

#        data = match.group("data")

    def feed(self, raw_data):
        assert isinstance(raw_data, str), "feed data must be unicode!"
        data = raw_data.strip()

        # cut out <pre> and <tt> areas block tag areas
        data = block_re.sub(self._pre_cut_out, data)
        data = inline_re.sub(self._pre_cut_out, data)

        # Delete whitespace from html code
        data = strip_html(data)

        if self.debugging:
            print("_" * 79)
            print("raw data:")
            print(repr(raw_data))
            print(" -" * 40)
            print("cleaned data:")
            print(data)
            print("-" * 79)
#            print(clean_data.replace(">", ">\n"))
#            print("-"*79)

        HTMLParser.feed(self, data)

        return self.root

    # -------------------------------------------------------------------------

    def _upto(self, node, kinds):
        """
        Look up the tree to the first occurence
        of one of the listed kinds of nodes or root.
        Start at the node node.
        """
        while node is not None and node.parent is not None:
            node = node.parent
            if node.kind in kinds:
                break

        return node

    def _go_up(self):
        kinds = list(BLOCK_TAGS) + ["document"]
        self.cur = self._upto(self.cur, kinds)
        self.debug_msg("go up to", self.cur)

    # -------------------------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        self.debug_msg("starttag", f"{tag!r} atts: {attrs}")

        if tag in IGNORE_TAGS:
            return

        headline = headline_tag_re.match(tag)
        if headline:
            self.cur = DocNode(
                "headline", self.cur, level=int(headline.group(1))
            )
            return

        if tag in ("li", "ul", "ol"):
            if tag in ("ul", "ol"):
                self.__list_level += 1
            self.cur = DocNode(tag, self.cur, None, attrs, level=self.__list_level)
        elif tag in ("img", "br"):
            # Work-a-round if img or br  tag is not marked as startendtag:
            # wrong: <img src="/image.jpg"> doesn't work if </img> not exist
            # right: <img src="/image.jpg" />
            DocNode(tag, self.cur, None, attrs)
        else:
            self.cur = DocNode(tag, self.cur, None, attrs)

    def handle_data(self, data):
        self.debug_msg("data", f"{data!r}")
        assert isinstance(data, str)
        DocNode("data", self.cur, content=data)

    def handle_charref(self, name):
        self.debug_msg("charref", f"{name!r}")
        DocNode("charref", self.cur, content=name)

    def handle_entityref(self, name):
        self.debug_msg("entityref", f"{name!r}")
        DocNode("entityref", self.cur, content=name)

    def handle_startendtag(self, tag, attrs):
        self.debug_msg("startendtag", f"{tag!r} atts: {attrs}")
        attr_dict = dict(attrs)
        if tag in (self._block_placeholder, self._inline_placeholder):
            id = int(attr_dict["id"])
#            block_type = attr_dict["type"]
            DocNode(
                f"{tag}_{attr_dict['type']}",
                self.cur,
                content=self.blockdata[id],
                #                attrs = attr_dict
            )
        else:
            DocNode(tag, self.cur, None, attrs)

    def handle_endtag(self, tag):
        if tag in IGNORE_TAGS:
            return

        self.debug_msg("endtag", f"{tag!r}")

        if tag == "br":  # handled in starttag
            return

        self.debug_msg("starttag", f"{self.get_starttag_text()!r}")

        if tag in ("ul", "ol"):
            self.__list_level -= 1

        if tag in BLOCK_TAGS or self.cur is None:
            self._go_up()
        else:
            self.cur = self.cur.parent

    # -------------------------------------------------------------------------

    def debug_msg(self, method, txt):
        if not self.debugging:
            return
        print(f"{str(self.getpos()):<8} {method:>8}: {txt}")

    def debug(self, start_node=None):
        """
        Display the current document tree
        """
        print("_" * 80)

        if start_node is None:
            start_node = self.root
            print("  document tree:")
        else:
            print(f"  tree from {start_node}:")

        print("=" * 80)

        def emit(node, ident=0):
            for child in node.children:
                txt = f"{' ' * ident}{child.kind}"

                if child.content:
                    txt += f": {child.content!r}"

                if child.attrs:
                    txt += f" - attrs: {child.attrs!r}"

                if child.level is not None:
                    txt += f" - level: {child.level!r}"

                print(txt)
                emit(child, ident + 4)
        emit(start_node)
        print("*" * 80)


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())

#    p = HtmlParser(debug=True)
#    p.feed("""\
# <p><span>in span</span><br />
# <code>in code</code></p>
# """)
#    p.debug()
