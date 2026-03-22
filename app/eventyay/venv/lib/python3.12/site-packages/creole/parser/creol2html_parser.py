"""
    Creole wiki markup parser

    See http://wikicreole.org/ for latest specs.

    Notes:
    * No markup allowed in headings.
      Creole 1.0 does not require us to support this.
    * No markup allowed in table headings.
      Creole 1.0 does not require us to support this.
    * No (non-bracketed) generic url recognition: this is "mission impossible"
      except if you want to risk lots of false positives. Only known protocols
      are recognized.
    * We do not allow ":" before "//" italic markup to avoid urls with
      unrecognized schemes (like wtf://server/path) triggering italic rendering
      for the rest of the paragraph.

    :copyleft: 2008-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import re
from pprint import pformat

from creole.parser.creol2html_rules import INLINE_FLAGS, INLINE_RULES, BlockRules, InlineRules, SpecialRules
from creole.shared.document_tree import DocNode


class CreoleParser:
    """
    Parse the raw text and create a document object
    that can be converted into output using Emitter.
    """
    # For pre escaping, in creole 1.0 done with ~:
    pre_escape_re = re.compile(
        SpecialRules.pre_escape, re.MULTILINE | re.VERBOSE | re.UNICODE
    )

    # for link descriptions:
    link_re = re.compile(
        '|'.join([InlineRules.image, InlineRules.linebreak, InlineRules.char]),
        re.VERBOSE | re.UNICODE
    )
    # for list items:
    item_re = re.compile(
        SpecialRules.item, re.VERBOSE | re.UNICODE | re.MULTILINE
    )

    # for table cells:
    cell_re = re.compile(SpecialRules.cell, re.VERBOSE | re.UNICODE)

    # For inline elements:
    inline_re = re.compile('|'.join(INLINE_RULES), INLINE_FLAGS)

    def __init__(self, raw, block_rules=None, blog_line_breaks=True, debug=False):
        assert isinstance(raw, str)
        self.raw = raw

        if block_rules is None:
            block_rules = BlockRules(blog_line_breaks=blog_line_breaks)

        self.blog_line_breaks = blog_line_breaks
        self.debug = debug  # TODO: use logging

        # setup block element rules:
        self.block_re = re.compile('|'.join(block_rules.rules), block_rules.re_flags)

        self.root = DocNode('document', None)
        self.cur = self.root        # The most recent document node
        self.text = None            # The node to add inline characters to
        self.last_text_break = None  # Last break node, inserted by _text_repl()

        # Filled with all macros that's in the text
        self.root.used_macros = set()

    # --------------------------------------------------------------------------

    def cleanup_break(self, old_cur):
        """
        remove unused end line breaks.
        Should be called before a new block element.
        e.g.:
          <p>line one<br />
          line two<br />     <--- remove this br-tag
          </p>
        """
        if self.cur.children:
            last_child = self.cur.children[-1]
            if last_child.kind == "break":
                del(self.cur.children[-1])

    def _upto(self, node, kinds):
        """
        Look up the tree to the first occurence
        of one of the listed kinds of nodes or root.
        Start at the node node.
        """
        self.cleanup_break(node)  # remove unused end line breaks.
        while node.parent is not None and node.kind not in kinds:
            node = node.parent

        return node

    def _upto_block(self):
        self.cur = self._upto(self.cur, ('document',))  # 'section', 'blockquote'))

    # __________________________________________________________________________
    # The _*_repl methods called for matches in regexps. Sometimes the
    # same method needs several names, because of group names in regexps.

    def _text_repl(self, groups):
        #        print("_text_repl()", self.cur.kind)
        #        self.debug_groups(groups)

        if self.cur.kind in ('table', 'table_row', 'bullet_list', 'number_list'):
            self._upto_block()

        if self.cur.kind in ('document', 'section', 'blockquote'):
            self.cur = DocNode('paragraph', self.cur)

        text = groups.get('text', "")

        if groups.get('space') and self.cur.children:
            # use wikipedia style line breaks and seperate a new line with one space
            text = " " + text

        self.parse_inline(text)

        if groups.get('break') and self.cur.kind in ('paragraph',
                                                     'emphasis', 'strong', 'pre_inline'):
            self.last_text_break = DocNode('break', self.cur, "")

        self.text = None
    _break_repl = _text_repl
    _space_repl = _text_repl

    def _url_repl(self, groups):
        """Handle raw urls in text."""
        if not groups.get('escaped_url'):
            # this url is NOT escaped
            target = groups.get('url_target', "")
            node = DocNode('link', self.cur)
            node.content = target
            DocNode('text', node, node.content)
            self.text = None
        else:
            # this url is escaped, we render it as text
            if self.text is None:
                self.text = DocNode('text', self.cur, "")
            self.text.content += groups.get('url_target')
    _url_target_repl = _url_repl
    _url_proto_repl = _url_repl
    _escaped_url_repl = _url_repl

    def _link_repl(self, groups):
        """Handle all kinds of links."""
        target = groups.get('link_target', "")
        text = (groups.get('link_text', "") or "").strip()
        parent = self.cur
        self.cur = DocNode('link', self.cur)
        self.cur.content = target
        self.text = None
        re.sub(self.link_re, self._replace, text)
        self.cur = parent
        self.text = None
    _link_target_repl = _link_repl
    _link_text_repl = _link_repl

    # --------------------------------------------------------------------------

    def _add_macro(self, groups, macro_type, name_key, args_key, text_key=None):
        """
        generic method to handle the macro, used for all variants:
        inline, inline-tag, block
        """
        # self.debug_groups(groups)
        assert macro_type in ("macro_inline", "macro_block")

        if text_key:
            macro_text = groups.get(text_key, "").strip()
        else:
            macro_text = None

        node = DocNode(macro_type, self.cur, macro_text)
        macro_name = groups[name_key]
        node.macro_name = macro_name
        self.root.used_macros.add(macro_name)
        node.macro_args = groups.get(args_key, "").strip()

        self.text = None

    def _macro_block_repl(self, groups):
        """
        block macro, e.g:
        <<macro args="foo">>
        some
        lines
        <</macro>>
        """
        self._upto_block()
        self.cur = self.root
        self._add_macro(
            groups,
            macro_type="macro_block",
            name_key="macro_block_start",
            args_key="macro_block_args",
            text_key="macro_block_text",
        )
    _macro_block_start_repl = _macro_block_repl
    _macro_block_args_repl = _macro_block_repl
    _macro_block_text_repl = _macro_block_repl

    def _macro_tag_repl(self, groups):
        """
        A single macro tag, e.g.: <<macro-a foo="bar">> or <<macro />>
        """
        self._add_macro(
            groups,
            macro_type="macro_inline",
            name_key="macro_tag_name",
            args_key="macro_tag_args",
            text_key=None,
        )
    _macro_tag_name_repl = _macro_tag_repl
    _macro_tag_args_repl = _macro_tag_repl

    def _macro_inline_repl(self, groups):
        """
        inline macro tag with data, e.g.: <<macro>>text<</macro>>
        """
        self._add_macro(
            groups,
            macro_type="macro_inline",
            name_key="macro_inline_start",
            args_key="macro_inline_args",
            text_key="macro_inline_text",
        )
    _macro_inline_start_repl = _macro_inline_repl
    _macro_inline_args_repl = _macro_inline_repl
    _macro_inline_text_repl = _macro_inline_repl

    # --------------------------------------------------------------------------

    def _image_repl(self, groups):
        """Handles images and attachemnts included in the page."""
        target = groups.get('image_target', "").strip()
        text = (groups.get('image_text', "") or "").strip()
        node = DocNode("image", self.cur, target)
        DocNode('text', node, text or node.content)
        self.text = None
    _image_target_repl = _image_repl
    _image_text_repl = _image_repl

    def _separator_repl(self, groups):
        self._upto_block()
        DocNode('separator', self.cur)

    def _item_repl(self, groups):
        """ List item """
        bullet = groups.get('item_head', "")
        text = groups.get('item_text', "")
        if bullet[-1] == '#':
            kind = 'number_list'
        else:
            kind = 'bullet_list'
        level = len(bullet) - 1
        lst = self.cur
        # Find a list of the same kind and level up the tree
        while (
            lst and not (
                lst.kind in (
                    'number_list',
                    'bullet_list') and lst.level == level) and lst.kind not in (
                'document',
                'section',
                'blockquote')):
            lst = lst.parent
        if lst and lst.kind == kind:
            self.cur = lst
        else:
            # Create a new level of list
            self.cur = self._upto(self.cur,
                                  ('list_item', 'document', 'section', 'blockquote'))
            self.cur = DocNode(kind, self.cur)
            self.cur.level = level
        self.cur = DocNode('list_item', self.cur)
        self.cur.level = level + 1
        self.parse_inline(text)
        self.text = None
    _item_text_repl = _item_repl
    _item_head_repl = _item_repl

    def _list_repl(self, groups):
        """ complete list """
        self.item_re.sub(self._replace, groups["list"])

    def _head_repl(self, groups):
        self._upto_block()
        node = DocNode('header', self.cur, groups['head_text'].strip())
        node.level = len(groups['head_head'])
        self.text = None
    _head_head_repl = _head_repl
    _head_text_repl = _head_repl

    def _table_repl(self, groups):
        row = groups.get('table', '|').strip()
        self.cur = self._upto(self.cur, (
            'table', 'document', 'section', 'blockquote'))
        if self.cur.kind != 'table':
            self.cur = DocNode('table', self.cur)
        tb = self.cur
        tr = DocNode('table_row', tb)

        for m in self.cell_re.finditer(row):
            cell = m.group('cell')
            if cell:
                text = cell.strip()
                self.cur = DocNode('table_cell', tr)
                self.text = None
            else:
                text = m.group('head').strip('= ')
                self.cur = DocNode('table_head', tr)
                self.text = DocNode('text', self.cur, "")
            self.parse_inline(text)

        self.cur = tb
        self.text = None

    def _pre_block_repl(self, groups):
        self._upto_block()
        kind = groups.get('pre_block_kind', None)
        text = groups.get('pre_block_text', "")

        def remove_tilde(m):
            return m.group('indent') + m.group('rest')
        text = self.pre_escape_re.sub(remove_tilde, text)
        node = DocNode('pre_block', self.cur, text)
        node.sect = kind or ''
        self.text = None
    _pre_block_text_repl = _pre_block_repl
    _pre_block_head_repl = _pre_block_repl
    _pre_block_kind_repl = _pre_block_repl

    def _line_repl(self, groups):
        """ Transfer newline from the original markup into the html code """
        self._upto_block()
        DocNode('line', self.cur, "")

    def _pre_inline_repl(self, groups):
        text = groups.get('pre_inline_text', "")
        DocNode('pre_inline', self.cur, text)
        self.text = None
    _pre_inline_text_repl = _pre_inline_repl
    _pre_inline_head_repl = _pre_inline_repl

    # --------------------------------------------------------------------------

    def _inline_mark(self, groups, key):
        self.cur = DocNode(key, self.cur)

        self.text = None
        text = groups[f"{key}_text"]
        self.parse_inline(text)

        self.cur = self._upto(self.cur, (key,)).parent
        self.text = None

    # TODO: How can we generalize that:

    def _emphasis_repl(self, groups):
        self._inline_mark(groups, key='emphasis')
    _emphasis_text_repl = _emphasis_repl

    def _strong_repl(self, groups):
        self._inline_mark(groups, key='strong')
    _strong_text_repl = _strong_repl

    def _monospace_repl(self, groups):
        self._inline_mark(groups, key='monospace')
    _monospace_text_repl = _monospace_repl

    def _superscript_repl(self, groups):
        self._inline_mark(groups, key='superscript')
    _superscript_text_repl = _superscript_repl

    def _subscript_repl(self, groups):
        self._inline_mark(groups, key='subscript')
    _subscript_text_repl = _subscript_repl

    def _underline_repl(self, groups):
        self._inline_mark(groups, key='underline')
    _underline_text_repl = _underline_repl

    def _small_repl(self, groups):
        self._inline_mark(groups, key='small')
    _small_text_repl = _small_repl

    def _delete_repl(self, groups):
        self._inline_mark(groups, key='delete')
    _delete_text_repl = _delete_repl

    # --------------------------------------------------------------------------

    def _linebreak_repl(self, groups):
        DocNode('break', self.cur, None)
        self.text = None

    def _escape_repl(self, groups):
        if self.text is None:
            self.text = DocNode('text', self.cur, "")
        self.text.content += groups.get('escaped_char', "")
    _escaped_char_repl = _escape_repl

    def _char_repl(self, groups):
        if self.text is None:
            self.text = DocNode('text', self.cur, "")
        self.text.content += groups.get('char', "")

    # --------------------------------------------------------------------------

    def _replace(self, match):
        """Invoke appropriate _*_repl method. Called for every matched group."""

        def debug(groups):
            data = dict([
                group for group in groups.items() if group[1] is not None
            ])
            print(pformat(data))

        groups = match.groupdict()
        for name, text in groups.items():
            if text is not None:
                if self.debug and name != "char":
                    # TODO: use logging
                    debug(groups)
                replace_method = getattr(self, f'_{name}_repl')
                replace_method(groups)
                return

    def parse_inline(self, raw):
        """Recognize inline elements inside blocks."""
        re.sub(self.inline_re, self._replace, raw)

    def parse_block(self, raw):
        """Recognize block elements."""
        re.sub(self.block_re, self._replace, raw)

    def parse(self):
        """Parse the text given as self.raw and return DOM tree."""
        # convert all lineendings to \n
        text = self.raw.replace("\r\n", "\n").replace("\r", "\n")
        if self.debug:
            # TODO: use logging
            print(repr(text))
        self.parse_block(text)
        return self.root

    # --------------------------------------------------------------------------

    def debug_tree(self, start_node=None):
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
                print(f"{' ' * ident}{child.kind}: {child.content!r}")
                emit(child, ident + 4)
        emit(start_node)
        print("*" * 80)

    def debug_groups(self, groups):
        print("_" * 80)
        print("  debug groups:")
        for name, text in groups.items():
            if text is not None:
                print(f"{name:>15}: {text!r}")
        print("-" * 80)


if __name__ == "__main__":
    import doctest
    print(doctest.testmod())

    print("-" * 80)

    txt = """A <<unittest_macro1 args="foo1">>bar1<</unittest_macro1>> in a line..."""

    print(txt)
    print("-" * 80)

    blog_line_breaks = False

    p = CreoleParser(txt, blog_line_breaks=blog_line_breaks)
    document = p.parse()
    p.debug()

    def display_match(match):
        groups = match.groupdict()
        for name, text in groups.items():
            if name != "char" and text is not None:
                print(f"{name:>20}: {text!r}")

    parser = CreoleParser("", blog_line_breaks=blog_line_breaks)

    print("_" * 80)
    print("merged block rules test:")
    re.sub(parser.block_re, display_match, txt)

    print("_" * 80)
    print("merged inline rules test:")
    re.sub(parser.inline_re, display_match, txt)

    def test_single(rules, flags, txt):
        for rule in rules:
            rexp = re.compile(rule, flags)
            rexp.sub(display_match, txt)

    print("_" * 80)
    print("single block rules match test:")
    block_rules = BlockRules()
    test_single(block_rules.rules, block_rules.re_flags, txt)

    print("_" * 80)
    print("single inline rules match test:")
    test_single(INLINE_RULES, INLINE_FLAGS, txt)

    print("---END---")
