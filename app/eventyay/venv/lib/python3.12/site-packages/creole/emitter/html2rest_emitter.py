"""
    html -> reStructuredText Emitter
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Links about reStructuredText:

    http://openalea.gforge.inria.fr/doc/openalea/doc/_build/html/source/sphinx/rest_syntax.html

    :copyleft: 2011-2012 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import posixpath

from creole.shared.base_emitter import BaseEmitter
from creole.shared.markup_table import MarkupTable


# Kink of nodes in which hyperlinks are stored in references intead of embedded urls.
DO_SUBSTITUTION = ("th", "td",)  # TODO: In witch kind of node must we also substitude links?


class Html2restException(Exception):
    pass


class ReStructuredTextEmitter(BaseEmitter):
    """
    Build from a document_tree (html2creole.parser.HtmlParser instance) a
    creole markup text.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.table_head_prefix = "_. "
        self.table_auto_width = False

        self._substitution_data = []
        self._used_substitution_links = {}
        self._used_substitution_images = {}
        self._list_markup = ""

    def _get_block_data(self):
        """
        return substitution bock data
        e.g.:
        .. _link text: /link/url/
        .. |substitution| image:: /image.png
        """
        content = "\n".join(self._substitution_data)
        self._substitution_data = []
        return content

    # --------------------------------------------------------------------------

    def blockdata_pre_emit(self, node):
        """ pre block -> with newline at the end """
        pre_block = self.deentity.replace_all(node.content).strip()
        pre_block = "\n".join(f"    {line}" for line in pre_block.splitlines())
        return f"::\n\n{pre_block}\n\n"

    def inlinedata_pre_emit(self, node):
        """ a pre inline block -> no newline at the end """
        return f"<pre>{self.deentity.replace_all(node.content)}</pre>"

    def blockdata_pass_emit(self, node):
        return f"{node.content}\n\n"

    # --------------------------------------------------------------------------

    def emit_children(self, node):
        """Emit all the children of a node."""
        return "".join(self.emit_children_list(node))

    def emit(self):
        """Emit the document represented by self.root DOM tree."""
        return self.emit_node(self.root).rstrip()

    def document_emit(self, node):
        self.last = node
        result = self.emit_children(node)
        if self._substitution_data:
            # add rest at the end
            if not result.endswith("\n\n"):
                result += "\n\n"
            result += f"{self._get_block_data()}\n\n"
        return result

    def emit_node(self, node):
        result = ""
        if self._substitution_data and node.parent == self.root:
            result += f"{self._get_block_data()}\n\n"

        result += super().emit_node(node)
        return result

    def p_emit(self, node):
        return f"{self.emit_children(node)}\n\n"

    HEADLINE_DATA = {
        1: ("=", True),
        2: ("-", True),
        3: ("=", False),
        4: ("-", False),
        5: ('`', False),
        6: ("'", False),
    }

    def headline_emit(self, node):
        text = self.emit_children(node)

        level = node.level
        if level > 6:
            level = 6

        char, both = self.HEADLINE_DATA[level]
        markup = char * len(text)

        if both:
            format = "%(m)s\n%(t)s\n%(m)s\n\n"
        else:
            format = "%(t)s\n%(m)s\n\n"

        return format % {"m": markup, "t": text}

    # --------------------------------------------------------------------------

    def _typeface(self, node, key):
        return key + self.emit_children(node) + key

    def strong_emit(self, node):
        return self._typeface(node, key="**")

    def b_emit(self, node):
        return self._typeface(node, key="**")
    big_emit = strong_emit

    def i_emit(self, node):
        return self._typeface(node, key="*")

    def em_emit(self, node):
        return self._typeface(node, key="*")

    def tt_emit(self, node):
        return self._typeface(node, key="``")

    def small_emit(self, node):
        # FIXME: Is there no small in ReSt???
        return self.emit_children(node)

#    def sup_emit(self, node):
#        return self._typeface(node, key="^")
#    def sub_emit(self, node):
#        return self._typeface(node, key="~")
#    def del_emit(self, node):
#        return self._typeface(node, key="-")
#
#    def cite_emit(self, node):
#        return self._typeface(node, key="??")
#    def ins_emit(self, node):
#        return self._typeface(node, key="+")
#
#    def span_emit(self, node):
#        return self._typeface(node, key="%")
#    def code_emit(self, node):
#        return self._typeface(node, key="@")

    # --------------------------------------------------------------------------

    def hr_emit(self, node):
        return "----\n\n"

    def _should_do_substitution(self, node):
        node = node.parent

        if node.kind in DO_SUBSTITUTION:
            return True

        if node is not self.root:
            return self._should_do_substitution(node)
        else:
            return False

    def _get_old_substitution(self, substitution_dict, text, url):
        if text not in substitution_dict:
            # save for the next time
            substitution_dict[text] = url
        else:
            # text has links with the same link text
            old_url = substitution_dict[text]
            if old_url == url:
                # same url -> substitution can be reused
                return old_url
            else:
                msg = (
                    "Duplicate explicit target name:"
                    " substitution was used more than one time, but with different URL."
                    " - link text: %r url1: %r url2: %r"
                ) % (text, old_url, url)
                raise Html2restException(msg)

    def a_emit(self, node):
        link_text = self.emit_children(node)
        url = node.attrs["href"]

        old_url = self._get_old_substitution(self._used_substitution_links, link_text, url)

        if self._should_do_substitution(node):
            # make a hyperlink reference
            if not old_url:
                # new substitution
                self._substitution_data.append(
                    f".. _{link_text}: {url}"
                )
            return f"`{link_text}`_"

        if old_url:
            # reuse a existing substitution
            return f"`{link_text}`_"
        else:
            # create a inline hyperlink
            return f"`{link_text} <{url}>`_"

    def img_emit(self, node):
        src = node.attrs["src"]

        if src.split(':')[0] == 'data':
            return ""

        title = node.attrs.get("title", "")
        alt = node.attrs.get("alt", "")
        if len(alt) > len(title):  # Use the longest one
            substitution_text = alt
        else:
            substitution_text = title

        if substitution_text == "":  # Use filename as picture text
            substitution_text = posixpath.basename(src)

        old_src = self._get_old_substitution(
            self._used_substitution_images, substitution_text, src
        )
        if not old_src:
            self._substitution_data.append(
                f".. |{substitution_text}| image:: {src}"
            )

        return f"|{substitution_text}|"

    # --------------------------------------------------------------------------

    def code_emit(self, node):
        return f"``{self._emit_content(node)}``"

    # --------------------------------------------------------------------------

    def li_emit(self, node):
        content = self.emit_children(node).strip("\n")
        result = f"\n{'    ' * (node.level - 1)}{self._list_markup} {content}\n"
        return result

    def _list_emit(self, node, list_type):
        self._list_markup = list_type
        content = self.emit_children(node)

        if node.level == 1:
            # FIXME: This should be made ​​easier and better
            complete_list = "\n\n".join(i.strip("\n") for i in content.split("\n") if i)
            content = f"{complete_list}\n\n"

        return content

    def ul_emit(self, node):
        return self._list_emit(node, "*")

    def ol_emit(self, node):
        return self._list_emit(node, "#.")

    def table_emit(self, node):
        """
        http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html#tables
        """
        self._table = MarkupTable(
            head_prefix="",
            auto_width=True,
            debug_msg=self.debug_msg
        )
        self.emit_children(node)
        content = self._table.get_rest_table()
        return f"{content}\n\n"
