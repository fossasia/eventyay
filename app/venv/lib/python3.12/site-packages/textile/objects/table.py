# -*- coding: utf-8 -*-
from xml.etree import ElementTree

from textile.regex_strings import (align_re_s, cls_re_s, regex_snippets,
                                   table_span_re_s, valign_re_s, pnct_re_s)
from textile.utils import generate_tag, parse_attributes

try:
    import regex as re
except ImportError:
    import re


class Table(object):
    caption_re = re.compile(
        (r'^\|\=(?P<capts>{s}{a}{c})\. '
         r'(?P<cap>[^\n]*)(?P<row>.*)'
         .format(**{'s': table_span_re_s, 'a': align_re_s, 'c': cls_re_s})),
        re.S)
    colgroup_re = re.compile(
        r'^\|:(?P<cols>{s}{a}{c}\. .*)'
        .format(**{'s': table_span_re_s, 'a': align_re_s, 'c': cls_re_s}),
        re.M)
    heading_re = re.compile(
        r'^_(?={0}|{1})'.format(regex_snippets['space'], pnct_re_s))

    def __init__(self, textile, tatts, rows, summary):
        self.textile = textile
        self.attributes = parse_attributes(tatts, 'table', restricted=self.textile.restricted)
        if summary:
            self.attributes.update(summary=summary.strip())
        self.input = rows
        self.caption = ''
        self.colgroup = ''
        self.content = []

    def process(self):
        rgrp = None
        groups = []
        split = (
            re.compile(r'\|{0}*?$'.format(regex_snippets['space']), re.M)
            .split(self.input))
        for i, row in enumerate([x for x in split if x]):
            row = row.lstrip()

            # Caption -- only occurs on row 1, otherwise treat '|=. foo |...'
            # as a normal center-aligned cell.
            cmtch = self.caption_re.match(row)
            if i == 0 and cmtch:
                caption = Caption(restricted=self.textile.restricted, **cmtch.groupdict())
                self.caption = '\n{0}'.format(caption.caption)
                row = cmtch.group('row').lstrip()
                if row == '':
                    continue

            # Colgroup -- A colgroup row will not necessarily end with a |.
            # Hence it may include the next row of actual table data.
            if row[:2] == '|:':
                if '\n' in row:
                    colgroup_data, row = row[2:].split('\n')
                else:
                    colgroup_data, row = row[2:], ''
                colgroup_atts, cols = colgroup_data, None
                if '|' in colgroup_data:
                    colgroup_atts, cols = colgroup_data.split('|', 1)
                colgrp = Colgroup(cols, colgroup_atts, restricted=self.textile.restricted)
                self.colgroup = colgrp.process()
                if row == '':
                    continue

            # search the row for a table group - thead, tfoot, or tbody
            grpmatchpattern = (r"(:?^\|(?P<part>{v})(?P<rgrpatts>{s}{a}{c})"
                               r"\.\s*$\n)?^(?P<row>.*)").format(
                                   **{'v': valign_re_s, 's': table_span_re_s,
                                      'a': align_re_s, 'c': cls_re_s})
            grpmatch_re = re.compile(grpmatchpattern, re.S | re.M)
            grpmatch = grpmatch_re.match(row.lstrip())

            grptypes = {'^': Thead, '~': Tfoot, '-': Tbody}
            if grpmatch.group('part'):
                # we're about to start a new group, so process the current one
                # and add it to the output
                if rgrp:
                    groups.append('\n\t{0}'.format(rgrp.process()))
                rgrp = grptypes[grpmatch.group('part')](grpmatch.group(
                    'rgrpatts'), restricted=self.textile.restricted)
            row = grpmatch.group('row')

            rmtch = re.search(r'^(?P<ratts>{0}{1}\. )(?P<row>.*)'.format(
                align_re_s, cls_re_s), row.lstrip())
            if rmtch:
                row_atts = parse_attributes(rmtch.group('ratts'), 'tr', restricted=self.textile.restricted)
                row = rmtch.group('row')
            else:
                row_atts = {}

            # create a row to hold the cells.
            r = Row(row_atts, row)
            for cellctr, cell in enumerate(row.split('|')[1:]):
                ctag = 'td'
                if self.heading_re.match(cell):
                    ctag = 'th'

                cmtch = re.search(r'^(?P<catts>_?{0}{1}{2}\. )'
                                  '(?P<cell>.*)'.format(
                                      table_span_re_s, align_re_s, cls_re_s),
                                  cell, flags=re.S)
                if cmtch:
                    catts = cmtch.group('catts')
                    cell_atts = parse_attributes(catts, 'td', restricted=self.textile.restricted)
                    cell = cmtch.group('cell')
                else:
                    cell_atts = {}

                if not self.textile.lite:
                    a_pattern = r'(?P<space>{0}*)(?P<cell>.*)'.format(
                        regex_snippets['space'])
                    a = re.search(a_pattern, cell, flags=re.S)
                    cell = self.textile.redcloth_list(a.group('cell'))
                    cell = self.textile.textileLists(cell)
                    cell = '{0}{1}'.format(a.group('space'), cell)

                # create a cell
                c = Cell(ctag, cell, cell_atts)
                cline_tag = '\n\t\t\t{0}'.format(c.process())
                # add the cell to the row
                r.cells.append(self.textile.doTagBr(ctag, cline_tag))

            # if we're in a group, add it to the group's rows, else add it
            # directly to the content
            if rgrp:
                rgrp.rows.append(r.process())
            else:
                self.content.append(r.process())

        # if there's still an rgrp, process it and add it to the output
        if rgrp:
            groups.append('\n\t{0}'.format(rgrp.process()))

        content = '{0}{1}{2}{3}\n\t'.format(
            self.caption, self.colgroup, ''.join(groups), ''.join(self.content))
        tbl = generate_tag('table', content, self.attributes)
        return '\t{0}\n\n'.format(tbl)


class Caption(object):
    def __init__(self, capts, cap, row, restricted):
        self.attributes = parse_attributes(capts, restricted=restricted)
        self.caption = self.process(cap)

    def process(self, cap):
        tag = generate_tag('caption', cap.strip(), self.attributes)
        return '\t{0}'.format(tag)


class Colgroup(object):
    def __init__(self, cols, atts, restricted):
        self.row = ''
        self.attributes = atts
        self.cols = cols
        self.restricted = restricted

    def process(self):
        enc = 'unicode'

        group_atts = parse_attributes(self.attributes, 'col', restricted=self.restricted)
        colgroup = ElementTree.Element('colgroup', attrib=group_atts)
        colgroup.text = '\n\t'
        if self.cols is not None:
            match_cols = self.cols.replace('.', '').split('|')
            # colgroup is the first item in match_cols, the remaining items are
            # cols.
            for idx, col in enumerate(match_cols):
                col_atts = parse_attributes(col.strip(), 'col', restricted=self.restricted)
                ElementTree.SubElement(colgroup, 'col', col_atts)
        colgrp = ElementTree.tostring(colgroup, encoding=enc)
        # cleanup the extra xml declaration if it exists, (python versions
        # differ) and then format the resulting string accordingly: newline and
        # tab between cols and a newline at the end
        xml_declaration = "<?xml version='1.0' encoding='UTF-8'?>\n"
        colgrp = colgrp.replace(xml_declaration, '')
        colgrp = colgrp.replace('><', '>\n\t<')
        return f"\n\t{colgrp}"


class Row(object):
    def __init__(self, attributes, row):
        self.tag = 'tr'
        self.attributes = attributes
        self.cells = []

    def process(self):
        output = []
        for c in self.cells:
            output.append(c)
        cell_data = '{0}\n\t\t'.format(''.join(output))
        tag = generate_tag('tr', cell_data, self.attributes)
        return '\n\t\t{0}'.format(tag)


class Cell(object):
    def __init__(self, tag, content, attributes):
        self.tag = tag
        self.content = content
        self.attributes = attributes

    def process(self):
        return generate_tag(self.tag, self.content, self.attributes)


class _TableSection(object):
    def __init__(self, tag, attributes, restricted):
        self.tag = tag
        self.attributes = parse_attributes(attributes, restricted=restricted)
        self.rows = []

    def process(self):
        return generate_tag(self.tag, '{0}\n\t'.format(''.join(self.rows)), self.attributes)


class Thead(_TableSection):
    def __init__(self, attributes, restricted):
        super(Thead, self).__init__('thead', attributes, restricted)


class Tbody(_TableSection):
    def __init__(self, attributes, restricted):
        super(Tbody, self).__init__('tbody', attributes, restricted)


class Tfoot(_TableSection):
    def __init__(self, attributes, restricted):
        super(Tfoot, self).__init__('tfoot', attributes, restricted)
