"""
    html -> textile Emitter
    ~~~~~~~~~~~~~~~~~~~~~~


    :copyleft: 2008-2011 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import posixpath

from creole.shared.base_emitter import BaseEmitter


class TextileEmitter(BaseEmitter):
    """
    Build from a document_tree (html2creole.parser.HtmlParser instance) a
    creole markup text.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.table_head_prefix = "_. "
        self.table_auto_width = False

    def emit(self):
        """Emit the document represented by self.root DOM tree."""
        return self.emit_node(self.root).strip()  # FIXME

    # --------------------------------------------------------------------------

    def blockdata_pre_emit(self, node):
        """ pre block -> with newline at the end """
        return f"<pre>{self.deentity.replace_all(node.content)}</pre>\n"

    def inlinedata_pre_emit(self, node):
        """ a pre inline block -> no newline at the end """
        return f"<pre>{self.deentity.replace_all(node.content)}</pre>"

    def blockdata_pass_emit(self, node):
        return f"{node.content}\n\n"

    # --------------------------------------------------------------------------

    def p_emit(self, node):
        return f"{self.emit_children(node)}\n\n"

    def headline_emit(self, node):
        return f"h{node.level:d}. {self.emit_children(node)}\n\n"

    # --------------------------------------------------------------------------

    def _typeface(self, node, key):
        return key + self.emit_children(node) + key

    def strong_emit(self, node):
        return self._typeface(node, key="*")

    def b_emit(self, node):
        return self._typeface(node, key="**")
    big_emit = strong_emit

    def i_emit(self, node):
        return self._typeface(node, key="__")

    def em_emit(self, node):
        return self._typeface(node, key="_")

    def sup_emit(self, node):
        return self._typeface(node, key="^")

    def sub_emit(self, node):
        return self._typeface(node, key="~")

    def del_emit(self, node):
        return self._typeface(node, key="-")

    def cite_emit(self, node):
        return self._typeface(node, key="??")

    def ins_emit(self, node):
        return self._typeface(node, key="+")

    def span_emit(self, node):
        return self._typeface(node, key="%")

    def code_emit(self, node):
        return self._typeface(node, key="@")

    # --------------------------------------------------------------------------

    def hr_emit(self, node):
        return "----\n\n"

    def a_emit(self, node):
        link_text = self.emit_children(node)
        url = node.attrs["href"]
        return f'"{link_text}":{url}'

    def img_emit(self, node):
        src = node.attrs["src"]

        if src.split(':')[0] == 'data':
            return ""

        title = node.attrs.get("title", "")
        alt = node.attrs.get("alt", "")
        if len(alt) > len(title):  # Use the longest one
            text = alt
        else:
            text = title

        if text == "":  # Use filename as picture text
            text = posixpath.basename(src)

        return f"!{src}({text})!"

    # --------------------------------------------------------------------------

    def ul_emit(self, node):
        return self._list_emit(node, list_type="*")

    def ol_emit(self, node):
        return self._list_emit(node, list_type="#")
