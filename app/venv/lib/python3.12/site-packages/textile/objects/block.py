# -*- coding: utf-8 -*-
from collections import OrderedDict
try:
    import regex as re
except ImportError:
    import re

from textile.regex_strings import cls_re_s, regex_snippets
from textile.utils import encode_html, generate_tag, parse_attributes


class Block(object):
    def __init__(self, textile, tag, atts, ext, cite, content):
        self.textile = textile
        self.tag = tag
        self.atts = atts
        self.ext = ext
        self.cite = cite
        self.content = content

        self.attributes = parse_attributes(atts, restricted=self.textile.restricted)
        self.outer_tag = ''
        self.inner_tag = ''
        self.outer_atts = OrderedDict()
        self.inner_atts = OrderedDict()
        self.eat = False
        self.process()

    def process(self):
        if self.tag == 'p':
            # is this an anonymous block with a note definition?
            notedef_re = re.compile(r"""
            ^note\#                               # start of note def marker
            (?P<label>[^%<*!@\#^([{{ {space}.]+)  # label
            (?P<link>[*!^]?)                      # link
            (?P<att>{cls})                        # att
            \.?                                   # optional period.
            [{space}]+                            # whitespace ends def marker
            (?P<content>.*)$                      # content""".format(
                space=regex_snippets['space'], cls=cls_re_s),
                flags=re.X | re.U)
            notedef = notedef_re.sub(self.textile.fParseNoteDefs, self.content)

            # It will be empty if the regex matched and ate it.
            if '' == notedef:
                self.content = notedef
                self.eat = True

        fns = re.search(r'fn(?P<fnid>{0}+)'.format(regex_snippets['digit']),
                        self.tag, flags=re.U)
        if fns:
            self.tag = 'p'
            fnid = self.textile.fn.get(fns.group('fnid'), None)
            if fnid is None:
                fnid = '{0}{1}'.format(self.textile.linkPrefix,
                                       self.textile._increment_link_index())

            # If there is an author-specified ID goes on the wrapper & the
            # auto-id gets pushed to the <sup>
            supp_id = OrderedDict()

            # if class has not been previously specified, set it to "footnote"
            if 'class' not in self.attributes:
                self.attributes.update({'class': 'footnote'})

            # if there's no specified id, use the generated one.
            if 'id' not in self.attributes:
                self.attributes.update({'id': 'fn{0}'.format(fnid)})
            else:
                supp_id = parse_attributes('(#fn{0})'.format(fnid), restricted=self.textile.restricted)

            if '^' not in self.atts:
                sup = generate_tag('sup', fns.group('fnid'), supp_id)
            else:
                fnrev = generate_tag('a', fns.group('fnid'), {'href':
                                     '#fnrev{0}'.format(fnid)})
                sup = generate_tag('sup', fnrev, supp_id)

            self.content = '{0} {1}'.format(sup, self.content)

        if self.tag == 'bq':
            if self.cite:
                self.cite = self.textile.shelveURL(self.cite)
                cite_att = OrderedDict(cite=self.cite)
                self.cite = ' cite="{0}"'.format(self.cite)
            else:
                self.cite = ''
                cite_att = OrderedDict()
            cite_att.update(self.attributes)
            self.outer_tag = 'blockquote'
            self.outer_atts = cite_att
            self.inner_tag = 'p'
            self.inner_atts = self.attributes
            self.eat = False

        elif self.tag == 'bc' or self.tag == 'pre':
            i_tag = ''
            if self.tag == 'bc':
                i_tag = 'code'
            content = encode_html(self.content)
            self.content = self.textile.shelve(content)
            self.outer_tag = 'pre'
            self.outer_atts = self.attributes
            self.inner_tag = i_tag
            self.inner_atts = self.attributes
            self.eat = False

        elif self.tag == 'notextile':
            self.content = self.textile.shelve(self.content)

        elif self.tag == '###':
            self.eat = True

        else:
            self.outer_tag = self.tag
            self.outer_atts = self.attributes

        if not self.eat:
            self.content = self.textile.graf(self.content)
        else:
            self.content = ''
