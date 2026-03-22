# -*- coding: utf-8 -*-
__copyright__ = """
Copyright (c) 2009, Jason Samsa, http://jsamsa.com/
Copyright (c) 2010, Kurt Raschke <kurt@kurtraschke.com>
Copyright (c) 2004, Roberto A. F. De Almeida, http://dealmeida.net/
Copyright (c) 2003, Mark Pilgrim, http://diveintomark.org/

Original PHP Version:
Copyright (c) 2003-2004, Dean Allen <dean@textism.com>
All rights reserved.

Thanks to Carlo Zottmann <carlo@g-blog.net> for refactoring
Textile's procedural code into a class framework

Additions and fixes Copyright (c) 2006 Alex Shiels http://thresholdstate.com/

"""
import uuid
from urllib.parse import urlparse, urlsplit, urlunsplit, quote, unquote
from collections import OrderedDict
from nh3 import clean

from textile.regex_strings import (align_re_s, cls_re_s, pnct_re_s,
                                   regex_snippets, syms_re_s, table_span_re_s)
from textile.utils import (decode_high, encode_high, encode_html, generate_tag,
                           getimagesize, has_raw_text, human_readable_url,
                           is_rel_url, is_valid_url, list_type,
                           normalize_newlines, parse_attributes, pba)
from textile.objects import Block, Table

try:
    import regex as re
except ImportError:
    import re


def make_glyph_replacers(html_type, uid, glyph_defs):
    """
    Generates a list of "replacers" (each is a pair consiting of
    a regular expression and a replacing pattern) that,
    when applied sequentially, replace some characters of the original
    text with their HTML codes to produce valid HTML.
    """
    cur = (
        r'(?:[{0}]{1}*)?'.format(regex_snippets['cur'], regex_snippets['space'])
        if regex_snippets['cur']
        else r'')
    pre_result = [
        # dimension sign (before apostrophes/quotes are replaced)
        (re.compile(
            r'([0-9]+[\])]?[\'"]? ?)[x]( ?[\[(]?)'
            r'(?=[+-]?{0}[0-9]*\.?[0-9]+)'.format(cur),
            flags=re.I | re.U),
         r'\1{dimension}\2'),
        # apostrophe's
        (re.compile(
            r"({0}|\))'({0})"
            .format(regex_snippets['wrd']),
            flags=re.U),
         r'\1{apostrophe}\2'),
        # back in '88
        (re.compile(
            r"({0})'(\d+{1}?)\b(?![.]?[{1}]*?')".format(
                regex_snippets['space'], regex_snippets['wrd']),
            flags=re.U),
         r'\1{apostrophe}\2'),
        # single opening following an open bracket.
        (re.compile(r"([([{])'(?=\S)", flags=re.U),
         r'\1{quote_single_open}'),
        # single closing
        (re.compile(
            r"(\S)'(?={0}|{1}|<|$)".format(regex_snippets['space'], pnct_re_s),
            flags=re.U),
         r'\1{quote_single_close}'),
        # single opening
        (re.compile(r"'", re.U), r'{quote_single_open}'),
        # double opening following an open bracket. Allows things like
        # Hello ["(Mum) & dad"]
        (re.compile(r'([([{])"(?=\S)', flags=re.U),
         r'\1{quote_double_open}'),
        # double closing
        (re.compile(
            r'(\S)"(?={0}|{1}|<|$)'.format(regex_snippets['space'], pnct_re_s),
            flags=re.U),
         r'\1{quote_double_close}'),
        # double opening
        (re.compile(r'"'), r'{quote_double_open}'),
        # ellipsis
        (re.compile(r'([^.]?)\.{3}'), r'\1{ellipsis}'),
        # em dash
        (re.compile(r'(\s?)--(\s?)'), r'\1{emdash}\2'),
        # en dash
        (re.compile(r' - '), r' {endash} '),
        # trademark
        (re.compile(
            r'(\b ?|{0}|^)[([]TM[])]'.format(regex_snippets['space']),
            flags=re.I | re.U),
         r'\1{trademark}'),
        # registered
        (re.compile(
            r'(\b ?|{0}|^)[([]R[])]'.format(regex_snippets['space']),
            flags=re.I | re.U),
            r'\1{registered}'),
        # copyright
        (re.compile(
            r'(\b ?|{0}|^)[([]C[])]'.format(regex_snippets['space']),
            flags=re.I | re.U),
         r'\1{copyright}'),
        # 1/2
        (re.compile(r'[([]1\/2[])]'), r'{half}'),
        # 1/4
        (re.compile(r'[([]1\/4[])]'), r'{quarter}'),
        # 3/4
        (re.compile(r'[([]3\/4[])]'), r'{threequarters}'),
        # degrees
        (re.compile(r'[([]o[])]'), r'{degrees}'),
        # plus/minus
        (re.compile(r'[([]\+\/-[])]'), r'{plusminus}'),
        # 3+ uppercase acronym
        (re.compile(
            r'\b([{0}][{1}]{{2,}})\b(?:[(]([^)]*)[)])'
            .format(regex_snippets['abr'], regex_snippets['acr']),
            flags=re.U),
         (r'<abbr title="\2">\1</abbr>' if html_type == 'html5'
          else r'<acronym title="\2">\1</acronym>')),
        # 3+ uppercase
        (re.compile(
            r'({space}|^|[>(;-])([{abr}]{{3,}})([{nab}]*)'
            '(?={space}|{pnct}|<|$)(?=[^">]*?(<|$))'
            .format(space=regex_snippets['space'],
                    abr=regex_snippets['abr'],
                    nab=regex_snippets['nab'],
                    pnct=pnct_re_s),
            re.U),
         r'\1<span class="caps">{0}:glyph:\2</span>\3'.format(uid)),
    ]
    return [(regex_obj, replacement.format(**glyph_defs))
            for (regex_obj, replacement) in pre_result]


class Textile(object):
    restricted_url_schemes = ('http', 'https', 'ftp', 'mailto')
    unrestricted_url_schemes = restricted_url_schemes + (
        'file', 'tel', 'callto', 'sftp', 'data')

    btag = ('bq', 'bc', 'notextile', 'pre', 'h[1-6]', r'fn\d+', 'p', '###')
    btag_lite = ('bq', 'bc', 'p')

    note_index = 1

    glyph_definitions = {
        'quote_single_open':  '&#8216;',  # noqa: E241
        'quote_single_close': '&#8217;',  # noqa: E241
        'quote_double_open':  '&#8220;',  # noqa: E241
        'quote_double_close': '&#8221;',  # noqa: E241
        'apostrophe':         '&#8217;',  # noqa: E241
        'prime':              '&#8242;',  # noqa: E241
        'prime_double':       '&#8243;',  # noqa: E241
        'ellipsis':           '&#8230;',  # noqa: E241
        'ampersand':          '&amp;',    # noqa: E241
        'emdash':             '&#8212;',  # noqa: E241
        'endash':             '&#8211;',  # noqa: E241
        'dimension':          '&#215;',   # noqa: E241
        'trademark':          '&#8482;',  # noqa: E241
        'registered':         '&#174;',   # noqa: E241
        'copyright':          '&#169;',   # noqa: E241
        'half':               '&#189;',   # noqa: E241
        'quarter':            '&#188;',   # noqa: E241
        'threequarters':      '&#190;',   # noqa: E241
        'degrees':            '&#176;',   # noqa: E241
        'plusminus':          '&#177;',   # noqa: E241
    }

    spanWrappers = (
        ('[', ']'),
    )

    def __init__(self, restricted=False, lite=False, noimage=False,
                 get_sizes=False, html_type='xhtml', rel='', block_tags=True):
        """Textile properties that are common to regular textile and
        textile_restricted"""
        self.restricted = restricted
        self.lite = lite
        self.noimage = noimage
        self.get_sizes = get_sizes
        self.fn = {}
        self.urlrefs = {}
        self.shelf = {}
        self.rel = rel
        self.html_type = html_type
        self.max_span_depth = 5
        self.span_depth = 0
        uid = uuid.uuid4().hex
        self.uid = 'textileRef:{0}:'.format(uid)
        self.linkPrefix = '{0}-'.format(uid)
        self.linkIndex = 0
        self.refCache = {}
        self.refIndex = 0
        self.block_tags = block_tags

        self.glyph_replacers = make_glyph_replacers(
            html_type, self.uid, self.glyph_definitions)

        if self.restricted is True:
            self.url_schemes = self.restricted_url_schemes
        else:
            self.url_schemes = self.unrestricted_url_schemes

        all_schemes_re_s = '|'.join([
            '(?:{0})'.format(scheme)
            for scheme in self.url_schemes
        ])
        self.url_ref_regex = re.compile(
            r'(?:(?<=^)|(?<=\s))\[(.+)\]\s?((?:{0}:\/\/|\/)\S+)(?=\s|$)'.format(all_schemes_re_s),
            re.U
        )

    def parse(self, text, rel=None, sanitize=False):
        """Parse the input text as textile and return html output."""
        self.notes = OrderedDict()
        self.unreferencedNotes = OrderedDict()
        self.notelist_cache = OrderedDict()

        if text.strip() == '':
            return text

        if self.restricted:
            text = encode_html(text, quotes=False)

        text = normalize_newlines(text)
        text = text.replace(self.uid, '')

        if self.block_tags:
            if self.lite:
                self.blocktag_allowlist = set(['bq', 'p', 'br'])
                text = self.block(text)
            else:
                self.blocktag_allowlist = set(['bq', 'p', 'br', 'bc', 'notextile',
                                               'pre', 'h[1-6]',
                                               f"fn{regex_snippets['digit']}+", '###'])
                text = self.block(text)
                text = self.placeNoteLists(text)
        else:
            # Inline markup (em, strong, sup, sub, del etc).
            text = self.span(text)

            # Glyph level substitutions (mainly typographic -- " & ' => curly
            # quotes, -- => em-dash etc.
            text = self.glyphs(text)

        if rel:
            self.rel = ' rel="{0}"'.format(rel)

        text = self.getRefs(text)

        if not self.lite:
            text = self.placeNoteLists(text)
        text = self.retrieve(text)
        text = text.replace('{0}:glyph:'.format(self.uid), '')

        if sanitize:
            text = clean(text, tags=self.blocktag_allowlist)

        text = self.retrieveTags(text)
        text = self.retrieveURLs(text)

        # if the text contains a break tag (<br> or <br />) not followed by
        # a newline, replace it with a new style break tag and a newline.
        text = re.sub(r'<br( /)?>(?!\n)', '<br />\n', text)

        text = text.rstrip('\n')

        return text

    def table(self, text):
        text = "{0}\n\n".format(text)
        pattern = re.compile(r'^(?:table(?P<tatts>_?{s}{a}{c})\.'
                             r'(?P<summary>.*?)\n)?^(?P<rows>{a}{c}\.? ?\|.*\|)'
                             r'[\s]*\n\n'.format(
                                 **{'s': table_span_re_s, 'a': align_re_s,
                                    'c': cls_re_s}), flags=re.S | re.M | re.U)
        match = pattern.search(text)
        if match:
            table = Table(self, **match.groupdict())
            return table.process()
        return text

    def textileLists(self, text):
        pattern = re.compile(r'^((?:[*;:]+|[*;:#]*#(?:_|\d+)?){0}[ .].*)$'
                             r'(?![^#*;:])'.format(cls_re_s), re.U | re.M | re.S)
        return pattern.sub(self.fTextileList, text)

    def fTextileList(self, match):
        text = re.split(r'\n(?=[*#;:])', match.group(), flags=re.M)
        pt = ''
        result = []
        ls = OrderedDict()
        for i, line in enumerate(text):
            try:
                nextline = text[i + 1]
            except IndexError:
                nextline = ''

            m = re.search(r"^(?P<tl>[#*;:]+)(?P<st>_|\d+)?(?P<atts>{0})[ .]"
                          "(?P<content>.*)$".format(cls_re_s), line, re.S)
            if m:
                tl, start, atts, content = m.groups()
                content = content.strip()
            else:
                result.append(line)
                continue

            nl = ''
            ltype = list_type(tl)
            tl_tags = {';': 'dt', ':': 'dd'}
            litem = tl_tags.get(tl[0], 'li')

            showitem = len(content) > 0

            # handle list continuation/start attribute on ordered lists
            if ltype == 'o':
                if not hasattr(self, 'olstarts'):
                    self.olstarts = {tl: 1}

                # does the first line of this ol have a start attribute
                if len(tl) > len(pt):
                    # no, set it to 1.
                    if start is None:
                        self.olstarts[tl] = 1
                    # yes, set it to the given number
                    elif start != '_':
                        self.olstarts[tl] = int(start)
                    # we won't need to handle the '_' case, we'll just
                    # print out the number when it's needed

                # put together the start attribute if needed
                if len(tl) > len(pt) and start is not None:
                    start = ' start="{0}"'.format(self.olstarts[tl])

                # This will only increment the count for list items, not
                # definition items
                if showitem:
                    # Assume properly formatted input
                    try:
                        self.olstarts[tl] = self.olstarts[tl] + 1
                    # if we get here, we've got some poor textile formatting.
                    # add this type of list to olstarts and assume we'll start
                    # it at 1. expect screwy output.
                    except KeyError:
                        self.olstarts[tl] = 1

            nm = re.match(r"^(?P<nextlistitem>[#\*;:]+)(_|[\d]+)?{0}"
                          r"[ .].*".format(cls_re_s), nextline)
            if nm:
                nl = nm.group('nextlistitem')

            # We need to handle nested definition lists differently.  If
            # the next tag is a dt (';') of a lower nested level than the
            # current dd (':'),
            if ';' in pt and ':' in tl:
                ls[tl] = 2

            atts = pba(atts, restricted=self.restricted)
            tabs = '\t' * len(tl)
            # If start is still None, set it to '', else leave the value that
            # we've already formatted.
            start = start or ''
            # if this item tag isn't in the list, create a new list and
            # item, else just create the item
            if tl not in ls:
                ls[tl] = 1
                itemtag = ("\n{0}\t<{1}>{2}".format(tabs, litem, content) if
                           showitem else '')
                line = "<{0}l{1}{2}>{3}".format(ltype, atts, start, itemtag)
            else:
                line = ("\t<{0}{1}>{2}".format(litem, atts, content) if
                        showitem else '')
            line = '{0}{1}'.format(tabs, line)
            if len(nl) <= len(tl):
                if showitem:
                    line = "{0}</{1}>".format(line, litem)
            # work backward through the list closing nested lists/items
            for k, v in reversed(list(ls.items())):
                if len(k) > len(nl):
                    if v != 2:
                        line = "{0}\n{1}</{2}l>".format(
                            line, tabs, list_type(k))
                    if len(k) > 1 and v != 2:
                        line = "{0}</{1}>".format(line, litem)
                    del ls[k]
            # Remember the current Textile tag:
            pt = tl
            result.append(line)
        return self.doTagBr(litem, "\n".join(result))

    def doTagBr(self, tag, input):
        return re.compile(r'<({0})([^>]*?)>(.*)(</\1>)'.format(re.escape(tag)),
                          re.S).sub(self.doBr, input)

    def doPBr(self, in_):
        return (re
                .compile(r'<(p|h[1-6])([^>]*?)>(.*)(</\1>)', re.S)
                .sub(self.fPBr, in_))

    def fPBr(self, m):
        content = m.group(3)
        content = (
            re.compile(r"<br[ ]*/?>{0}*\n(?![{0}|])".format(regex_snippets['space']),
                       re.I)
            .sub("\n", content))
        content = re.compile(r"\n(?![\s|])").sub('<br />', content)
        return '<{0}{1}>{2}{3}'.format(m.group(1), m.group(2), content, m.group(4))

    def doBr(self, match):
        content = (
            re.compile(
                r'(.+)(?!(?<=</dd>|</dt>|</li>|<br/>)'
                r'|(?<=<br>)|(?<=<br />))\n(?![#*;:\s|])',
                re.I)
            .sub(r'\1<br />', match.group(3)))
        return '<{0}{1}>{2}{3}'.format(match.group(1), match.group(2), content,
                                       match.group(4))

    def block(self, text):
        if not self.lite:
            tre = '|'.join(self.btag)
        else:
            tre = '|'.join(self.btag_lite)
        # split the text by two or more newlines, retaining the newlines in the
        # split list
        text = re.split(r'(\n{2,})', text)

        # some blocks, when processed, will ask us to output nothing, if that's
        # the case, we'd want to drop the whitespace which follows it.
        eat_whitespace = False

        # check to see if previous block has already been escaped
        escaped = False

        # check if multiline paragraph (p..) tags <p>..</p> are added to line
        multiline_para = False

        tag = 'p'
        atts = cite = ext = ''

        out = []

        for line in text:
            # the line is just whitespace, add it to the output, and move on
            if not line.strip():
                if not eat_whitespace:
                    out.append(line)
                continue

            eat_whitespace = False

            pattern = (r'^(?P<tag>{0})(?P<atts>{1}{2})\.(?P<ext>\.?)'
                       r'(?::(?P<cite>\S+))? (?P<content>.*)$'.format(
                           tre, align_re_s, cls_re_s))
            match = re.search(pattern, line, flags=re.S | re.U)
            # tag specified on this line.
            if match:
                # if we had a previous extended tag but not this time, close up
                # the tag
                if ext and out:
                    # it's out[-2] because the last element in out is the
                    # whitespace that preceded this line
                    if not escaped:
                        content = encode_html(out[-2], quotes=True)
                        escaped = True
                    else:
                        content = out[-2]

                    if not multiline_para:
                        # block will have been defined in a previous run of the
                        # loop
                        content = generate_tag(block.inner_tag, content,  # noqa: F821
                                               block.inner_atts)  # noqa: F821
                        content = generate_tag(block.outer_tag, content,  # noqa: F821
                                               block.outer_atts)  # noqa: F821
                    out[-2] = content
                tag, atts, ext, cite, content = match.groups()
                block = Block(self, **match.groupdict())
                inner_block = generate_tag(block.inner_tag, block.content,
                                           block.inner_atts)
                # code tags and raw text won't be indented inside outer_tag.
                if block.inner_tag != 'code' and not has_raw_text(inner_block):
                    inner_block = "\n\t\t{0}\n\t".format(inner_block)
                if ext:
                    line = block.content
                else:
                    line = generate_tag(block.outer_tag, inner_block,
                                        block.outer_atts)
                    # pre tags and raw text won't be indented.
                    if block.outer_tag != 'pre' and not has_raw_text(line):
                        line = "\t{0}".format(line)

            # set having paragraph tags to false
                if block.tag == 'p' and ext:
                    multiline_para = False
            # no tag specified
            else:
                # if we're inside an extended block, add the text from the
                # previous line to the front.
                if ext and out:
                    if block.tag == 'p':
                        line = generate_tag(block.tag, line, block.outer_atts)
                        multiline_para = True
                    line = '{0}{1}'.format(out.pop(), line)
                # the logic in the if statement below is a bit confusing in
                # php-textile. I'm still not sure I understand what the php
                # code is doing. Something tells me it's a phpsadness. Anyway,
                # this works, and is much easier to understand: if we're not in
                # an extension, and the line doesn't begin with a space, treat
                # it like a block to insert. Lines that begin with a space are
                # not processed as a block.
                if not ext and not line[0] == ' ':
                    block = Block(self, tag, atts, ext, cite, line)
                    # if the block contains html tags, generate_tag would
                    # mangle it, so process as is.
                    if block.tag == 'p' and not has_raw_text(block.content):
                        line = block.content
                    else:
                        line = generate_tag(block.outer_tag, block.content,
                                            block.outer_atts)
                        line = "\t{0}".format(line)
                else:
                    if block.tag in ('pre', 'notextile') or block.inner_tag == 'code':
                        line = self.shelve(encode_html(line, quotes=True))
                    else:
                        line = self.graf(line)

                    if block.tag == 'p':
                        escaped = True

            if block.tag == 'p' and ext and not multiline_para:
                line = generate_tag(block.tag, line, block.outer_atts)
                multiline_para = True
            else:
                line = self.doPBr(line)
            if not block.tag == 'p':
                multiline_para = False

            line = line.replace('<br>', '<br />')

            # if we're in an extended block, and we haven't specified a new
            # tag, join this line to the last item of the output
            if ext and not match:
                last_item = out.pop()
                out.append('{0}{1}'.format(last_item, line))
            elif not block.eat:
                # or if it's a type of block which indicates we shouldn't drop
                # it, add it to the output.
                out.append(line)

            if not ext:
                tag = 'p'
                atts = ''
                cite = ''

            # if it's a block we should drop, don't keep the whitespace which
            # will come after it.
            if block.eat:
                eat_whitespace = True

        # at this point, we've gone through all the lines. if there's still an
        # extension in effect, we close it here
        if ext and out and not block.tag == 'p':
            content = out.pop()
            content = generate_tag(block.inner_tag, content, block.inner_atts)
            content = generate_tag(block.outer_tag, content, block.outer_atts)
            out.append(content)
        return ''.join(out)

    def footnoteRef(self, text):
        # somehow php-textile gets away with not capturing the space.
        return re.compile(r'(?<=\S)\[(?P<id>{0}+)(?P<nolink>!?)\]'
                          r'(?P<space>{1}?)'.format(
                              regex_snippets['digit'], regex_snippets['space']),
                          re.U).sub(self.footnoteID, text)

    def footnoteID(self, m):
        fn_att = OrderedDict({'class': 'footnote'})
        if m.group('id') not in self.fn:
            self.fn[m.group('id')] = '{0}{1}'.format(
                self.linkPrefix, self._increment_link_index())
            fnid = self.fn[m.group('id')]
            fn_att['id'] = 'fnrev{0}'.format(fnid)
        fnid = self.fn[m.group('id')]
        footref = generate_tag('a', m.group('id'), {'href': '#fn{0}'.format(
            fnid)})
        if '!' == m.group('nolink'):
            footref = m.group('id')
        footref = generate_tag('sup', footref, fn_att)
        return '{0}{1}'.format(footref, m.group('space'))

    def glyphs(self, text):
        """
        Because of the split command, the regular expressions are different for
        when the text at the beginning and the rest of the text.
        for example:
        let's say the raw text provided is "*Here*'s some textile"
        before it gets to this glyphs method, the text has been converted to
        "<strong>Here</strong>'s some textile"
        When run through the split, we end up with ["<strong>", "Here",
        "</strong>", "'s some textile"].  The re.search that follows tells it
        not to ignore html tags.
        If the single quote is the first character on the line, it's an open
        single quote.  If it's the first character of one of those splits, it's
        an apostrophe or closed single quote, but the regex will bear that out.
        A similar situation occurs for double quotes as well.
        So, for the first pass, we use a set of regexes from
        the initial_glyph_replacers. For all remaining passes,
        we use glyph_replacers
        """
        text = text.rstrip('\n')
        result = []
        standalone_amp_re = re.compile(
            r"&(?!#[0-9]+;|#x[a-f0-9]+;|[a-z][a-z0-9]*;)",
            flags=re.I)
        html_amp_symbol = self.glyph_definitions['ampersand']
        # split the text by any angle-bracketed tags
        lines = re.compile(r'(<[\w/!?].*?>)', re.U | re.S).split(text)
        for i, line in enumerate(lines):
            if i % 2 == 0:
                if not self.restricted:
                    # Raw < > & chars have already been encoded
                    # when in restricted mode
                    line = (
                        standalone_amp_re
                        .sub(html_amp_symbol, line)
                        .replace('<', '&lt;')
                        .replace('>', '&gt;'))
                for s, r in self.glyph_replacers:
                    line = s.sub(r, line)
            result.append(line)
        return ''.join(result)

    def getRefs(self, text):
        """Capture and store URL references in self.urlrefs."""
        return self.url_ref_regex.sub(self.refs, text)

    def refs(self, match):
        flag, url = match.groups()
        self.urlrefs[flag] = url
        return ''

    def relURL(self, url):
        scheme = urlparse(url)[0]
        if scheme and scheme not in self.url_schemes:
            return '#'
        return url

    def shelve(self, text):
        self.refIndex = self.refIndex + 1
        itemID = '{0}{1}:shelve'.format(self.uid, self.refIndex)
        self.shelf[itemID] = text
        return itemID

    def retrieve(self, text):
        while True:
            old = text
            for k, v in self.shelf.items():
                text = text.replace(k, v)
            if text == old:
                break
        return text

    def graf(self, text):
        if not self.lite:
            text = self.noTextile(text)
            text = self.code(text)

        text = self.getHTMLComments(text)

        text = self.getRefs(text)
        text = self.links(text)

        if not self.noimage:
            text = self.image(text)

        if not self.lite:
            text = self.table(text)
            text = self.redcloth_list(text)
            text = self.textileLists(text)

        text = self.span(text)
        text = self.footnoteRef(text)
        text = self.noteRef(text)
        text = self.glyphs(text)

        return text.rstrip('\n')

    def links(self, text):
        """For some reason, the part of the regex below that matches the url
        does not match a trailing parenthesis.  It gets caught by tail, and
        we check later to see if it should be included as part of the url."""
        text = self.markStartOfLinks(text)

        return self.replaceLinks(text)

    def markStartOfLinks(self, text):
        """Finds and marks the start of well formed links in the input text."""
        # Slice text on '":<not space>' boundaries. These always occur in
        # inline links between the link text and the url part and are much more
        # infrequent than '"' characters so we have less possible links to
        # process.
        slice_re = re.compile(r'":(?={0})'.format(regex_snippets['char']))
        slices = slice_re.split(text)
        output = []

        if len(slices) > 1:
            # There are never any start of links in the last slice, so pop it
            # off (we'll glue it back later).
            last_slice = slices.pop()

            for s in slices:
                # If there is no possible start quote then this slice is not
                # a link
                if '"' not in s:
                    output.append(s)
                    continue
                # Cut this slice into possible starting points wherever we find
                # a '"' character. Any of these parts could represent the start
                # of the link text - we have to find which one.
                possible_start_quotes = s.split('"')

                # Start our search for the start of the link with the closest
                # prior quote mark.
                possibility = possible_start_quotes.pop()

                # Init the balanced count. If this is still zero at the end of
                # our do loop we'll mark the " that caused it to balance as the
                # start of the link and move on to the next slice.
                balanced = 0
                linkparts = []
                i = 0

                while balanced != 0 or i == 0:  # pragma: no branch
                    # Starting at the end, pop off the previous part of the
                    # slice's fragments.

                    # Add this part to those parts that make up the link text.
                    linkparts.append(possibility)

                    if len(possibility) > 0:
                        # did this part inc or dec the balanced count?
                        if re.search(r'^\S|=$', possibility, flags=re.U):  # pragma: no branch
                            balanced = balanced - 1
                        if re.search(r'\S$', possibility, flags=re.U):  # pragma: no branch
                            balanced = balanced + 1
                        try:
                            possibility = possible_start_quotes.pop()
                        except IndexError:
                            break
                    else:
                        # If quotes occur next to each other, we get zero
                        # length strings.  eg. ...""Open the door,
                        # HAL!"":url...  In this case we count a zero length in
                        # the last position as a closing quote and others as
                        # opening quotes.
                        if i == 0:
                            balanced = balanced + 1
                        else:
                            balanced = balanced - 1
                        i = i + 1

                        try:
                            possibility = possible_start_quotes.pop()
                        except IndexError:  # pragma: no cover
                            # If out of possible starting segments we back the
                            # last one from the linkparts array
                            linkparts.pop()
                            break
                        # If the next possibility is empty or ends in a space
                        # we have a closing ".
                        if (possibility == '' or possibility.endswith(' ')):
                            # force search exit
                            balanced = 0

                    if balanced <= 0:
                        possible_start_quotes.append(possibility)
                        break

                # Rebuild the link's text by reversing the parts and sticking
                # them back together with quotes.
                linkparts.reverse()
                link_content = '"'.join(linkparts)
                # Rebuild the remaining stuff that goes before the link but
                # that's already in order.
                pre_link = '"'.join(possible_start_quotes)
                # Re-assemble the link starts with a specific marker for the
                # next regex.
                o = '{0}{1}linkStartMarker:"{2}'.format(pre_link, self.uid,
                                                        link_content)
                output.append(o)

            # Add the last part back
            output.append(last_slice)
            # Re-assemble the full text with the start and end markers
            text = '":'.join(output)

        return text

    def replaceLinks(self, text):
        """Replaces links with tokens and stores them on the shelf."""
        stopchars = r"\s|^'\"*"
        pattern = r"""
            (?P<pre>\[)?           # Optionally open with a square bracket eg. Look ["here":url]
            {0}linkStartMarker:"   # marks start of the link
            (?P<inner>(?:.|\n)*?)  # grab the content of the inner "..." part of the link, can be anything but
                                   # do not worry about matching class, id, lang or title yet
            ":                     # literal ": marks end of atts + text + title block
            (?P<urlx>[^{1}]*)      # url upto a stopchar
        """.format(self.uid, stopchars)
        text = re.compile(pattern, flags=re.X | re.U).sub(self.fLink, text)
        return text

    def fLink(self, m):
        in_ = m.group()
        pre, inner, url = m.groups()
        pre = pre or ''

        if inner == '':
            return '{0}"{1}":{2}'.format(pre, inner, url)

        m = re.search(r'''^
            (?P<atts>{0})                # $atts (if any)
            {1}*                         # any optional spaces
            (?P<text>                    # $text is...
                (!.+!)                   #     an image
            |                            #   else...
                .+?                      #     link text
            )                            # end of $text
            (?:\((?P<title>[^)]+?)\))?   # $title (if any)
            $'''.format(cls_re_s, regex_snippets['space']), inner,
                      flags=re.X | re.U)

        atts = (m and m.group('atts')) or ''
        text = (m and m.group('text')) or inner
        title = (m and m.group('title')) or ''

        pop, tight = '', ''
        counts = {'[': None, ']': url.count(']'), '(': None, ')': None}

        # Look for footnotes or other square-bracket delimited stuff at the end
        # of the url...
        #
        # eg. "text":url][otherstuff... will have "[otherstuff" popped back
        # out.
        #
        # "text":url?q[]=x][123]    will have "[123]" popped off the back, the
        # remaining closing square brackets will later be tested for balance
        if (counts[']']):
            m = re.search(r'(?P<url>^.*\])(?P<tight>\[.*?)$', url, flags=re.U)
            if m:
                url, tight = m.groups()

        # Split off any trailing text that isn't part of an array assignment.
        # eg. "text":...?q[]=value1&q[]=value2 ... is ok
        # "text":...?q[]=value1]following  ... would have "following" popped
        # back out and the remaining square bracket will later be tested for
        # balance
        if (counts[']']):
            m = re.search(r'(?P<url>^.*\])(?!=)(?P<end>.*?)$', url, flags=re.U)
            url = m.group('url')
            tight = '{0}{1}'.format(m.group('end'), tight)

        # Now we have the array of all the multi-byte chars in the url we will
        # parse the  uri backwards and pop off  any chars that don't belong
        # there (like . or , or unmatched brackets of various kinds).
        first = True
        popped = True

        counts[']'] = url.count(']')
        url_chars = list(url)

        def _endchar(c, pop, popped, url_chars, counts, pre):
            """Textile URL shouldn't end in these characters, we pop them off
            the end and push them out the back of the url again."""
            pop = '{0}{1}'.format(c, pop)
            url_chars.pop()
            popped = True
            return pop, popped, url_chars, counts, pre

        def _rightanglebracket(c, pop, popped, url_chars, counts, pre):
            url_chars.pop()
            urlLeft = ''.join(url_chars)

            m = re.search(r'(?P<url_chars>.*)(?P<tag><\/[a-z]+)$', urlLeft)
            url_chars = m.group('url_chars')
            pop = '{0}{1}{2}'.format(m.group('tag'), c, pop)
            popped = True
            return pop, popped, url_chars, counts, pre

        def _closingsquarebracket(c, pop, popped, url_chars, counts, pre):
            """If we find a closing square bracket we are going to see if it is
            balanced.  If it is balanced with matching opening bracket then it
            is part of the URL else we spit it back out of the URL."""
            # If counts['['] is None, count the occurrences of '['
            counts['['] = counts['['] or url.count('[')

            if counts['['] == counts[']']:
                # It is balanced, so keep it
                url_chars.append(c)
            else:
                # In the case of un-matched closing square brackets we just eat
                # it
                popped = True
                url_chars.pop()
                counts[']'] = counts[']'] - 1
                if first:  # pragma: no branch
                    pre = ''
            return pop, popped, url_chars, counts, pre

        def _closingparenthesis(c, pop, popped, url_chars, counts, pre):
            if counts[')'] is None:  # pragma: no branch
                counts['('] = url.count('(')
                counts[')'] = url.count(')')

            if counts['('] != counts[')']:
                # Unbalanced so spit it out the back end
                popped = True
                pop = '{0}{1}'.format(url_chars.pop(), pop)
                counts[')'] = counts[')'] - 1
            return pop, popped, url_chars, counts, pre

        def _casesdefault(c, pop, popped, url_chars, counts, pre):
            return pop, popped, url_chars, counts, pre

        cases = {
            '!': _endchar,
            '?': _endchar,
            ':': _endchar,
            ';': _endchar,
            '.': _endchar,
            ',': _endchar,
            '>': _rightanglebracket,
            ']': _closingsquarebracket,
            ')': _closingparenthesis,
        }
        for c in url_chars[-1::-1]:  # pragma: no branch
            popped = False
            pop, popped, url_chars, counts, pre = cases.get(
                c, _casesdefault)(c, pop, popped, url_chars, counts, pre)
            first = False
            if popped is False:
                break

        url = ''.join(url_chars)
        uri_parts = urlsplit(url)

        scheme_in_list = uri_parts.scheme in self.url_schemes
        valid_scheme = (uri_parts.scheme and scheme_in_list)
        if not is_valid_url(url) and not valid_scheme:
            return in_.replace('{0}linkStartMarker:'.format(self.uid), '')

        if text == '$':
            if valid_scheme:
                text = human_readable_url(url)
            else:
                ref_url = self.urlrefs.get(url)
                if ref_url is not None:
                    text = human_readable_url(ref_url)
                else:
                    text = url

        text = text.strip()
        title = encode_html(title)

        if not self.noimage:  # pragma: no branch
            text = self.image(text)
        text = self.span(text)
        text = self.glyphs(text)
        url = self.shelveURL(self.encode_url(urlunsplit(uri_parts)))
        attributes = parse_attributes(atts, restricted=self.restricted)
        attributes['href'] = url
        if title:
            # if the title contains unicode data, it is annoying to get Python
            # 2.6 and all the latter versions working properly.  But shelving
            # the title is a quick and dirty solution.
            attributes['title'] = self.shelve(title)
        if self.rel:
            attributes['rel'] = self.rel
        a_text = generate_tag('a', text, attributes)
        a_shelf_id = self.shelve(a_text)

        out = '{0}{1}{2}{3}'.format(pre, a_shelf_id, pop, tight)

        return out

    def encode_url(self, url):
        """
        Converts a (unicode) URL to an ASCII URL, with the domain part
        IDNA-encoded and the path part %-encoded (as per RFC 3986).

        Fixed version of the following code fragment from Stack Overflow:
            http://stackoverflow.com/a/804380/72656
        """
        # parse it
        parsed = urlsplit(url)

        if parsed.netloc:
            # divide the netloc further
            netloc_pattern = re.compile(r"""
                (?:(?P<user>[^:@]+)(?::(?P<password>[^:@]+))?@)?
                (?P<host>[^:]+)
                (?::(?P<port>[0-9]+))?
            """, re.X | re.U)
            netloc_parsed = netloc_pattern.match(parsed.netloc).groupdict()
        else:
            netloc_parsed = {'user': '', 'password': '', 'host': '', 'port': ''}

        # encode each component
        scheme = parsed.scheme
        user = netloc_parsed['user'] and quote(netloc_parsed['user'])
        password = (
            netloc_parsed['password'] and quote(netloc_parsed['password'])
        )
        host = netloc_parsed['host']
        port = netloc_parsed['port'] and netloc_parsed['port']
        # the below splits the path portion of the url by slashes, translates
        # percent-encoded characters back into strings, then re-percent-encodes
        # what's necessary. Sounds screwy, but the url could include encoded
        # slashes, and this is a way to clean that up. It branches for PY2/3
        # because the quote and unquote functions expects different input
        # types: unicode strings for PY2 and str for PY3.
        path_parts = (quote(unquote(pce), b'') for pce in
                      parsed.path.split('/'))
        path = '/'.join(path_parts)

        # put it back together
        netloc = ''
        if user:
            netloc = '{0}{1}'.format(netloc, user)
            if password:
                netloc = '{0}:{1}'.format(netloc, password)
            netloc = '{0}@'.format(netloc)
        netloc = '{0}{1}'.format(netloc, host)
        if port:
            netloc = '{0}:{1}'.format(netloc, port)
        return urlunsplit((scheme, netloc, path, parsed.query, parsed.fragment))

    def span(self, text):
        qtags = (r'\*\*', r'\*', r'\?\?', r'\-', r'__',
                 r'_', r'%', r'\+', r'~', r'\^')
        pnct = r""".,"'?!;:‹›«»„“”‚‘’"""
        self.span_depth = self.span_depth + 1

        if self.span_depth <= self.max_span_depth:
            for tag in qtags:
                pattern = re.compile(r"""
                    (?P<pre>^|(?<=[\s>{pnct}\(])|[{{[])
                    (?P<tag>{tag})(?!{tag})
                    (?P<atts>{cls})
                    (?!{tag})
                    (?::(?P<cite>\S+[^{tag}]{space}))?
                    (?P<content>[^{space}{tag}]+|\S.*?[^\s{tag}\n])
                    (?P<end>[{pnct}]*)
                    {tag}
                    (?P<tail>$|[\[\]}}<]|(?=[{pnct}]{{1,2}}[^0-9]|\s|\)))
                """.format(
                    **{'tag': tag, 'cls': cls_re_s, 'pnct': pnct, 'space':
                        regex_snippets['space']}
                ), flags=re.X | re.U)
                text = pattern.sub(self.fSpan, text)
        self.span_depth = self.span_depth - 1
        return text

    def getSpecialOptions(self, pre, tail):
        for before, after in self.spanWrappers:
            if pre == before and tail == after:
                pre = tail = ''
                break
        return (pre, tail)

    def fSpan(self, match):
        pre, tag, atts, cite, content, end, tail = match.groups()
        pre, tail = self.getSpecialOptions(pre, tail)

        qtags = {
            '*':  'strong',  # noqa: E241
            '**': 'b',       # noqa: E241
            '??': 'cite',    # noqa: E241
            '_':  'em',      # noqa: E241
            '__': 'i',       # noqa: E241
            '-':  'del',     # noqa: E241
            '%':  'span',    # noqa: E241
            '+':  'ins',     # noqa: E241
            '~':  'sub',     # noqa: E241
            '^':  'sup'      # noqa: E241
        }

        tag = qtags[tag]
        atts = pba(atts, restricted=self.restricted)
        if cite:
            atts = '{0} cite="{1}"'.format(atts, cite.rstrip())

        content = self.span(content)
        opentag = '<{0}{1}>'.format(tag, atts)
        closetag = '</{0}>'.format(tag)
        tags = self.storeTags(opentag, closetag)
        return pre + tags['open'] + content + end + tags['close'] + tail

    def storeTags(self, opentag, closetag=''):
        tags = {}
        self.refIndex += 1
        self.refCache[self.refIndex] = opentag
        tags['open'] = self.uid + str(self.refIndex) + ':ospan '

        self.refIndex += 1
        self.refCache[self.refIndex] = closetag
        tags['close'] = ' ' + self.uid + str(self.refIndex) + ':cspan'
        return tags

    def retrieveTags(self, text):
        text = (re.compile('{0}(?P<token>[0-9]+):ospan '.format(self.uid), re.U)
                .sub(self.fRetrieveTags, text))
        text = (re.compile(' {0}(?P<token>[0-9]+):cspan'.format(self.uid), re.U)
                .sub(self.fRetrieveTags, text))
        return text

    def fRetrieveTags(self, match):
        return self.refCache[int(match.group('token'))]

    def image(self, text):
        pattern = re.compile(r"""
            (?:[\[{{])?                # pre
            \!                         # opening !
            (\<|\=|\>)?                # optional alignment atts
            ({0})                      # optional style,class atts
            (?:\.\s)?                  # optional dot-space
            ([^\s(!]+)                 # presume this is the src
            \s?                        # optional space
            (?:\(([^\)]+)\))?          # optional title
            \!                         # closing
            (?::(\S+)(?<![\]).,]))?    # optional href sans final punct
            (?:[\]}}]|(?=[.,\s)|]|$))  # lookahead: space or end of string
        """.format(cls_re_s), re.U | re.X)
        return pattern.sub(self.fImage, text)

    def fImage(self, match):
        # (None, '', '/imgs/myphoto.jpg', None, None)
        align, attributes, url, title, href = match.groups()
        atts = OrderedDict()
        size = None

        alignments = {'<': 'left', '=': 'center', '>': 'right'}

        if not title:
            title = ''

        if not is_rel_url(url) and self.get_sizes:
            size = getimagesize(url)

        if href:
            href = self.shelveURL(href)

        url = self.shelveURL(url)

        if align:
            atts.update(align=alignments[align])
        atts.update(alt=title)
        if size:
            atts.update(height="{0}".format(size[1]))
        atts.update(src=url)
        if attributes:
            atts.update(parse_attributes(attributes, restricted=self.restricted))
        if title:
            atts.update(title=title)
        if size:
            atts.update(width="{0}".format(size[0]))
        img = generate_tag('img', ' /', atts)
        if href:
            a_atts = OrderedDict(href=href)
            if self.rel:
                a_atts.update(rel=self.rel)
            img = generate_tag('a', img, a_atts)
        return img

    def code(self, text):
        text = self.doSpecial(text, '<code>', '</code>', self.fCode)
        text = self.doSpecial(text, '@', '@', self.fCode)
        text = self.doSpecial(text, '<pre>', '</pre>', self.fPre)
        return text

    def fCode(self, match):
        before, text, after = match.groups()
        after = after or ''
        before, after = self.getSpecialOptions(before, after)
        # text needs to be escaped
        text = encode_html(text, quotes=False)
        return ''.join([before, self.shelve('<code>{0}</code>'.format(text)), after])

    def fPre(self, match):
        before, text, after = match.groups()
        if after is None:
            after = ''
        before, after = self.getSpecialOptions(before, after)
        # text needs to be escaped
        text = encode_html(text)
        return ''.join([before, '<pre>', self.shelve(text), '</pre>', after])

    def doSpecial(self, text, start, end, method):
        pattern = re.compile(r'(^|\s|[\[({{>|]){0}(.*?){1}($|[\])}}])?'.format(
            re.escape(start), re.escape(end)), re.M | re.S)
        return pattern.sub(method, text)

    def noTextile(self, text):
        text = self.doSpecial(text, '<notextile>', '</notextile>',
                              self.fTextile)
        return self.doSpecial(text, '==', '==', self.fTextile)

    def fTextile(self, match):
        before, notextile, after = match.groups()
        if after is None:  # pragma: no branch
            after = ''
        before, after = self.getSpecialOptions(before, after)
        return ''.join([before, self.shelve(notextile), after])

    def getHTMLComments(self, text):
        """Search the string for HTML comments, e.g. <!-- comment text -->.  We
        send the text that matches this to fParseHTMLComments."""
        return self.doSpecial(text, '<!--', '-->', self.fParseHTMLComments)

    def fParseHTMLComments(self, match):
        """If self.restricted is True, clean the matched contents of the HTML
        comment.  Otherwise, return the comments unchanged.
        The original php had an if statement in here regarding restricted mode.
        nose reported that this line wasn't covered.  It's correct.  In
        restricted mode, the html comment tags have already been converted to
        &lt;!*#8212; and &#8212;&gt; so they don't match in getHTMLComments,
        and never arrive here.
        """
        before, commenttext, after = match.groups()
        commenttext = self.shelve(commenttext)
        return '{0}<!--{1}-->'.format(before, commenttext)

    def redcloth_list(self, text):
        """Parse the text for definition lists and send them to be
        formatted."""
        pattern = re.compile(r"^([-]+{0}[ .].*:=.*)$(?![^-])".format(cls_re_s),
                             re.M | re.U | re.S)
        return pattern.sub(self.fRCList, text)

    def fRCList(self, match):
        """Format a definition list."""
        out = []
        text = re.split(r'\n(?=[-])', match.group(), flags=re.M)
        for line in text:
            # parse the attributes and content
            m = re.match(r'^[-]+({0})[ .](.*)$'.format(cls_re_s), line,
                         flags=re.M | re.S)
            if not m:
                continue

            atts, content = m.groups()
            # cleanup
            content = content.strip()
            atts = pba(atts, restricted=self.restricted)

            # split the content into the term and definition
            xm = re.match(
                r'^(.*?){0}*:=(.*?){0}*(=:|:=)?{0}*$'
                .format(regex_snippets['space']),
                content,
                re.S)
            term, definition, _ = xm.groups()
            # cleanup
            term = term.strip()
            definition = definition.strip(' ')

            # if this is the first time through, out as a bool is False
            if not out:
                if definition == '':
                    dltag = "<dl{0}>".format(atts)
                else:
                    dltag = "<dl>"
                out.append(dltag)

            if term != '':
                is_newline_started_def = definition.startswith('\n')
                definition = (
                    definition
                    .strip()
                    .replace('\n', '<br />'))

                if is_newline_started_def:
                    definition = '<p>{0}</p>'.format(definition)
                term = term.replace('\n', '<br />')

                term = self.graf(term)
                definition = self.graf(definition)

                out.append('\t<dt{0}>{1}</dt>'.format(atts, term))
                if definition:
                    out.append('\t<dd>{0}</dd>'.format(definition))

        out.append('</dl>')
        out = '\n'.join(out)
        return out

    def placeNoteLists(self, text):
        """Parse the text for endnotes."""
        if self.notes:
            o = OrderedDict()
            for label, info in self.notes.items():
                if 'seq' in info:
                    i = info['seq']
                    info['seq'] = label
                    o[i] = info
                else:
                    self.unreferencedNotes[label] = info

            if o:  # pragma: no branch
                # sort o by key
                o = OrderedDict(sorted(o.items(), key=lambda t: t[0]))
            self.notes = o
        text_re = re.compile(r'<p>notelist({0})(?:\:([\w|{1}]))?([\^!]?)(\+?)'
                             r'\.?[\s]*</p>'.format(cls_re_s, syms_re_s), re.U)
        text = text_re.sub(self.fNoteLists, text)
        return text

    def fNoteLists(self, match):
        """Given the text that matches as a note, format it into HTML."""
        att, start_char, g_links, extras = match.groups()
        start_char = start_char or 'a'
        index = '{0}{1}{2}'.format(g_links, extras, start_char)
        result = ''

        if index not in self.notelist_cache:  # pragma: no branch
            o = []
            if self.notes:  # pragma: no branch
                for seq, info in self.notes.items():
                    links = self.makeBackrefLink(info, g_links, start_char)
                    atts = ''
                    if 'def' in info:
                        infoid = info['id']
                        atts = info['def']['atts']
                        content = info['def']['content']
                        li = ('\t\t<li{0}>{1}<span id="note{2}"> '
                              '</span>{3}</li>').format(atts, links, infoid,
                                                        content)
                    else:
                        li = ('\t\t<li{0}>{1} Undefined Note [#{2}].</li>'
                              ).format(atts, links, info['seq'])
                    o.append(li)
            if '+' == extras and self.unreferencedNotes:
                for seq, info in self.unreferencedNotes.items():
                    atts = info['def']['atts']
                    content = info['def']['content']
                    li = '\t\t<li{0}>{1}</li>'.format(atts, content)
                    o.append(li)
            self.notelist_cache[index] = "\n".join(o)
            result = self.notelist_cache[index]
        if result:
            list_atts = pba(att, restricted=self.restricted)
            result = '<ol{0}>\n{1}\n\t</ol>'.format(list_atts, result)
        return result

    def makeBackrefLink(self, info, g_links, i):
        """Given the pieces of a back reference link, create an <a> tag."""
        link = ''
        if 'def' in info:
            link = info['def']['link']
        backlink_type = link or g_links
        i_ = encode_high(i)
        allow_inc = i not in syms_re_s
        i_ = int(i_)

        if backlink_type == "!":
            return ''
        elif backlink_type == '^':
            return """<sup><a href="#noteref{0}">{1}</a></sup>""".format(
                info['refids'][0], i)
        else:
            result = []
            for refid in info['refids']:
                i_entity = decode_high(i_)
                sup = """<sup><a href="#noteref{0}">{1}</a></sup>""".format(
                    refid, i_entity)
                if allow_inc:
                    i_ = i_ + 1
                result.append(sup)
            result = ' '.join(result)
            return result

    def fParseNoteDefs(self, m):
        """Parse the note definitions and format them as HTML"""
        label = m.group('label')
        link = m.group('link')
        att = m.group('att')
        content = m.group('content')

        # Assign an id if the note reference parse hasn't found the label yet.
        if label not in self.notes:
            self.notes[label] = {'id': '{0}{1}'.format(
                self.linkPrefix, self._increment_link_index())}

        # Ignores subsequent defs using the same label
        if 'def' not in self.notes[label]:  # pragma: no branch
            self.notes[label]['def'] = {
                'atts': pba(att, restricted=self.restricted), 'content':
                self.graf(content), 'link': link}
        return ''

    def noteRef(self, text):
        """Search the text looking for note references."""
        text_re = re.compile(r"""
        \[          # start
        ({0})       # !atts
        \#
        ([^\]!]+)   # !label
        ([!]?)      # !nolink
        \]""".format(cls_re_s), re.X)
        text = text_re.sub(self.fParseNoteRefs, text)
        return text

    def fParseNoteRefs(self, match):
        """Parse and format the matched text into note references.
        By the time this function is called, all the defs will have been
        processed into the notes array. So now we can resolve the link numbers
        in the order we process the refs..."""
        atts, label, nolink = match.groups()
        atts = pba(atts, restricted=self.restricted)
        nolink = nolink == '!'

        # Assign a sequence number to this reference if there isn't one already
        if label in self.notes:
            num = self.notes[label]['seq']
        else:
            self.notes[label] = {
                'seq': self.note_index, 'refids': [], 'id': ''
            }
            num = self.note_index
            self.note_index = self.note_index + 1

        # Make our anchor point and stash it for possible use in backlinks when
        # the note list is generated later...
        refid = '{0}{1}'.format(self.linkPrefix, self._increment_link_index())
        self.notes[label]['refids'].append(refid)

        # If we are referencing a note that hasn't had the definition parsed
        # yet, then assign it an ID...
        if not self.notes[label]['id']:
            self.notes[label]['id'] = '{0}{1}'.format(
                self.linkPrefix, self._increment_link_index())
        labelid = self.notes[label]['id']

        # Build the link (if any)...
        result = '<span id="noteref{0}">{1}</span>'.format(refid, num)
        if not nolink:
            result = '<a href="#note{0}">{1}</a>'.format(labelid, result)

        # Build the reference...
        result = '<sup{0}>{1}</sup>'.format(atts, result)
        return result

    def shelveURL(self, text):
        if text == '':
            return ''
        self.refIndex = self.refIndex + 1
        self.refCache[self.refIndex] = text
        output = '{0}{1}{2}'.format(self.uid, self.refIndex, ':url')
        return output

    def retrieveURLs(self, text):
        return re.sub(r'{0}(?P<token>[0-9]+):url'.format(self.uid), self.retrieveURL, text)

    def retrieveURL(self, match):
        url = self.refCache.get(int(match.group('token')), '')
        if url == '':
            return url

        if url in self.urlrefs:
            url = self.urlrefs[url]

        return url

    def _increment_link_index(self):
        """The self.linkIndex property needs to be incremented in various
        places.  Don't Repeat Yourself."""
        self.linkIndex = self.linkIndex + 1
        return self.linkIndex


def textile(text, html_type='xhtml'):
    """
    Apply Textile to a block of text.

    This function takes the following additional parameters:

    html_type - 'xhtml' or 'html5' style tags (default: 'xhtml')

    """
    return Textile(html_type=html_type).parse(text)


def textile_restricted(text, lite=True, noimage=True, html_type='xhtml'):
    """
    Apply Textile to a block of text, with restrictions designed for weblog
    comments and other untrusted input.  Raw HTML is escaped, style attributes
    are disabled, and rel='nofollow' is added to external links.

    This function takes the following additional parameters:

    html_type - 'xhtml' or 'html5' style tags (default: 'xhtml')
    lite - restrict block tags to p, bq, and bc, disable tables (default: True)
    noimage - disable image tags (default: True)

    """
    return Textile(restricted=True, lite=lite, noimage=noimage,
                   html_type=html_type, rel='nofollow').parse(text)
