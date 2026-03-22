"""
    A clean reStructuredText html writer
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    It will produce a minimal set of html output.
    (No extry divs, classes oder ids.)

    Some code stolen from:
    http://www.arnebrodowski.de/blog/write-your-own-restructuredtext-writer.html
    https://github.com/alex-morega/docutils-plainhtml/blob/master/plain_html_writer.py

    :copyleft: 2011-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import sys

from creole.exceptions import DocutilsImportError


try:
    import docutils
    from docutils.core import publish_parts
    from docutils.writers import html4css1
except ImportError:
    etype, evalue, etb = sys.exc_info()
    msg = (
        "%s - You can't use rest2html!"
        " Please install: http://pypi.python.org/pypi/docutils"
    ) % evalue
    evalue = etype(msg)

    # Doesn't work with Python 3:
    # http://www.python-forum.de/viewtopic.php?f=1&t=27507
    # raise DocutilsImportError, evalue, etb

    raise DocutilsImportError(msg)


DEBUG = False
#DEBUG = True

IGNORE_ATTR = (
    "start", "class", "frame", "rules",
)
IGNORE_TAGS = (
    "div",
)


class CleanHTMLWriter(html4css1.Writer):
    """
    This docutils writer will use the CleanHTMLTranslator class below.
    """

    def __init__(self):
        html4css1.Writer.__init__(self)
        self.translator_class = CleanHTMLTranslator


class CleanHTMLTranslator(html4css1.HTMLTranslator):
    """
    Clean html translator for docutils system.
    """

    def _do_nothing(self, node, *args, **kwargs):
        pass

    def starttag(self, node, tagname, suffix='\n', empty=0, **attributes):
        """
        create start tag with the filter IGNORE_TAGS and IGNORE_ATTR.
        """
#        return super(CleanHTMLTranslator, self).starttag(node, tagname, suffix, empty, **attributes)
#        return "XXX%r" % tagname

        if tagname in IGNORE_TAGS:
            if DEBUG:
                print(f"ignore tag {tagname!r}")
            return ""

        parts = [tagname]
        for name, value in sorted(attributes.items()):
            # value=None was used for boolean attributes without
            # value, but this isn't supported by XHTML.
            assert value is not None

            name = name.lower()

            if name in IGNORE_ATTR:
                continue

            if isinstance(value, list):
                value = ' '.join(str(x) for x in value)

            part = f'{name.lower()}="{self.attval(str(value))}"'
            parts.append(part)

        if DEBUG:
            print(
                f'Tag {tagname!r}'
                f' - ids: {getattr(node, "ids", "-")!r}'
                f' - attributes: {attributes!r}'
                f' - parts: {parts!r}'
            )

        if empty:
            infix = ' /'
        else:
            infix = ''
        html = f"<{' '.join(parts)}{infix}>{suffix}"
        if DEBUG:
            print(f"startag html: {html!r}")
        return html

    def visit_section(self, node):
        self.section_level += 1

    def depart_section(self, node):
        self.section_level -= 1

    set_class_on_child = _do_nothing
    set_first_last = _do_nothing

    # remove <blockquote> (e.g. in nested lists)
    visit_block_quote = _do_nothing
    depart_block_quote = _do_nothing

    # set only html_body, we used in rest2html() and don't surround it with <div>
    def depart_document(self, node):
        self.html_body.extend(
            self.body_prefix[1:] + self.body_pre_docinfo + self.docinfo + self.body + self.body_suffix[:-1]
        )
        assert not self.context, f'len(context) = {len(self.context)}'

    # __________________________________________________________________________
    # Clean table:

    visit_thead = _do_nothing
    depart_thead = _do_nothing
    visit_tbody = _do_nothing
    depart_tbody = _do_nothing

    def visit_table(self, node):
        if docutils.__version__ > "0.10":
            self.context.append(self.compact_p)
            self.compact_p = True
        self.body.append(self.starttag(node, 'table'))

    def visit_tgroup(self, node):
        node.stubs = []

    def visit_field_list(self, node):
        super().visit_field_list(node)
        if "<col" in self.body[-1]:
            del(self.body[-1])

    def depart_field_list(self, node):
        self.body.append('</table>\n')
        self.compact_field_list, self.compact_p = self.context.pop()

    def visit_docinfo(self, node):
        self.body.append(self.starttag(node, 'table'))

    def depart_docinfo(self, node):
        self.body.append('</table>\n')

    # __________________________________________________________________________
    # Clean image:

    depart_figure = _do_nothing

    def visit_image(self, node):
        super().visit_image(node)
        if self.body[-1].startswith('<img'):
            align = None

            if 'align' in node:
                # image with alignment
                align = node['align']

            elif node.parent.tagname == 'figure' and 'align' in node.parent:
                # figure with alignment
                align = node.parent['align']

            if align:
                self.body[-1] = self.body[-1].replace(' />', f' align="{align}" />')


def rest2html(content, enable_exit_status=None, **kwargs):
    """
    Convert reStructuredText markup to clean html code: No extra div, class or ids.

    >>> rest2html("- bullet list")
    '<ul>\\n<li>bullet list</li>\\n</ul>\\n'

    >>> rest2html("A ReSt link to `PyLucid CMS <http://www.pylucid.org>`_ :)")
    '<p>A ReSt link to <a href="http://www.pylucid.org">PyLucid CMS</a> :)</p>\\n'

    >>> rest2html("========", enable_exit_status=1, traceback=False, exit_status_level=2)
    Traceback (most recent call last):
    ...
    SystemExit: 13
    """
    assert isinstance(content, str), f"rest2html content must be {str}, but it's {type(content)}"

    settings_overrides = {
        "input_encoding": "unicode",
        "doctitle_xform": False,
        "file_insertion_enabled": False,
        "raw_enabled": False,
    }
    settings_overrides.update(kwargs)

    parts = publish_parts(
        source=content,
        writer=CleanHTMLWriter(),
        settings_overrides=settings_overrides,
        enable_exit_status=enable_exit_status,
    )
#    import pprint
#    pprint.pprint(parts)
    return parts["html_body"]  # Don't detache the first heading


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())

#    print(rest2html(""")
# +------------+------------+
# | Headline 1 | Headline 2 |
# +============+============+
# | cell one   | cell two   |
# +------------+------------+
#    """)

#    print(rest2html(""")
#:homepage:
#  http://code.google.com/p/python-creole/
#
#:sourcecode:
#  http://github.com/jedie/python-creole
#    """)

    print(rest2html("""
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
    """))
