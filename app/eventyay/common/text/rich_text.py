"""Helpers for rich-text / HTML field content."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

from django.utils.html import strip_tags
from django.utils.text import Truncator


# Zero-width / format characters that look empty but survive str.strip().
_INVISIBLE_CHARS_RE = re.compile('[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff\u00ad]')
# Block tags produced by the rich-text editor, which always wraps content in them.
# Text without any of them is treated as plain text, even if it mentions inline tags like <a>.
_RICH_TEXT_TAG_RE = re.compile(
    r'</?(?:p|br|div|h[1-6]|ul|ol|li|blockquote|pre|table|thead|tbody|tr|td|th)(?:\s[^<>]*)?/?>',
    re.IGNORECASE,
)
_LIST_LINE_RE = re.compile(r'\s*(?:- |\d+\. )')
_LIST_MARKER_SPACING_RE = re.compile(r'^(\s*(?:- |\d+\. ))\s+')
_WHITESPACE_RE = re.compile(r'\s+')
_EXTRA_BLANK_LINES_RE = re.compile(r'\n{3,}')
# Private-use characters that mark preformatted text, whose indentation must be kept.
PRE_START = '\ue000'
PRE_END = '\ue001'
BLOCK_TAGS = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'table'}
LIST_TAGS = {'ul', 'ol'}
SKIPPED_TAGS = {'script', 'style'}


def is_empty_rich_text(value) -> bool:
    """Return True when value is empty or only whitespace / empty HTML tags."""
    if value is None:
        return True
    text = html.unescape(strip_tags(str(value)))
    text = _INVISIBLE_CHARS_RE.sub('', text).replace('\xa0', ' ').strip()
    return not text


class PlainTextHTMLParser(HTMLParser):
    """Collect the text of rich-text HTML, keeping paragraphs, line breaks, lists and link targets."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.lists = []
        self.link_href = None
        self.link_start = 0
        self.pre_depth = 0
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            if not self.lists:
                self.parts.append('\n\n')
            else:
                # A list item may hold several blocks; put each one after the first on a new line.
                item_text = ''.join(self.parts[self.lists[-1]['item_start'] :])
                if item_text.strip() and not item_text.endswith('\n'):
                    self.parts.append('\n')
        if tag in SKIPPED_TAGS:
            self.skip_depth += 1
        elif tag == 'br':
            self.parts.append('\n')
        elif tag in LIST_TAGS:
            if not self.lists:
                self.parts.append('\n\n')
            start = dict(attrs).get('start') if tag == 'ol' else None
            try:
                count = int(start) - 1
            except (TypeError, ValueError):
                count = 0
            self.lists.append({'ordered': tag == 'ol', 'count': count, 'item_start': len(self.parts)})
        elif tag == 'li':
            if not self.lists:
                self.lists.append({'ordered': False, 'count': 0, 'item_start': len(self.parts)})
            current = self.lists[-1]
            current['count'] += 1
            marker = f'{current["count"]}. ' if current['ordered'] else '- '
            self.parts.append('\n' + '  ' * (len(self.lists) - 1) + marker)
            current['item_start'] = len(self.parts)
        elif tag == 'a':
            self.link_href = dict(attrs).get('href')
            self.link_start = len(self.parts)
        elif tag == 'pre':
            self.pre_depth += 1
            self.parts.append(PRE_START)

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if tag == 'pre' and self.pre_depth:
            self.pre_depth -= 1
            self.parts.append(PRE_END)
        if tag in BLOCK_TAGS and not self.lists:
            self.parts.append('\n\n')
        elif tag == 'tr':
            self.parts.append('\n')
        elif tag in ('td', 'th'):
            self.parts.append(' ')
        elif tag in LIST_TAGS and self.lists:
            self.lists.pop()
            if not self.lists:
                self.parts.append('\n\n')
        elif tag == 'a' and self.link_href:
            label = ''.join(self.parts[self.link_start :]).strip()
            if self.link_href not in label:
                self.parts.append(f' ({self.link_href})')
            self.link_href = None

    def handle_data(self, data):
        if self.skip_depth:
            return
        if not self.pre_depth:
            data = _WHITESPACE_RE.sub(' ', data)
        self.parts.append(data)


def rich_text_to_plain_text(value) -> str:
    """Convert rich-text HTML to plain text, keeping paragraphs, line breaks, lists and link targets.

    Used where HTML cannot be rendered, such as iCal descriptions. Values without rich-text
    markup (plain text or Markdown) are returned unchanged.
    """
    if value is None:
        return ''
    value = str(value)
    if not _RICH_TEXT_TAG_RE.search(value):
        return value.strip()
    parser = PlainTextHTMLParser()
    parser.feed(value)
    parser.close()
    text = ''.join(parser.parts).replace('\xa0', ' ')
    lines = []
    in_pre = False
    for raw_line in text.splitlines():
        keep_indent = in_pre or PRE_START in raw_line
        in_pre = keep_indent and PRE_END not in raw_line
        line = raw_line.replace(PRE_START, '').replace(PRE_END, '')
        if keep_indent:
            lines.append(line.rstrip())
        elif _LIST_LINE_RE.match(line):
            lines.append(_LIST_MARKER_SPACING_RE.sub(r'\1', line.rstrip()))
        else:
            lines.append(line.strip())
    return _EXTRA_BLANK_LINES_RE.sub('\n\n', '\n'.join(lines)).strip()


_PREVIEW_TAG_RE = re.compile(
    r'</?(?:p|br|div|h[1-6]|ul|ol|li|blockquote|pre|table|thead|tbody|tr|td|th|a|script|style)(?:\s[^<>]*)?/?>',
    re.IGNORECASE,
)


class PreviewTextHTMLParser(HTMLParser):
    """Collect single-line plain text from rich-text HTML for metadata previews."""

    def __init__(self, max_collect: int | None = None):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth: int = 0
        self.max_collect: int | None = max_collect
        self.collected_chars: int = 0
        self.stopped_early: bool = False

    def _append_space(self) -> None:
        if self.parts and not self.parts[-1].endswith(' '):
            self.parts.append(' ')

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIPPED_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return
        if tag in BLOCK_TAGS or tag in LIST_TAGS or tag in ('li', 'br'):
            self._append_space()

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED_TAGS:
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return
        if self.skip_depth > 0:
            return
        if tag in BLOCK_TAGS or tag in LIST_TAGS or tag in ('li', 'tr', 'td', 'th'):
            self._append_space()

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return
        self.parts.append(data)
        self.collected_chars += len(data)
        if self.max_collect is not None and self.collected_chars >= self.max_collect:
            self.stopped_early = True
            raise StopIteration


def rich_text_to_preview_text(value: str | None, max_chars: int = 200) -> str:
    """Convert rich-text HTML or plain text into a single-line preview truncated to max_chars."""
    if value is None:
        return ''
    value = str(value)
    if not _PREVIEW_TAG_RE.search(value):
        clean_text = ' '.join(value.replace('\xa0', ' ').split())
        return Truncator(clean_text).chars(max_chars, truncate='…')

    parser = PreviewTextHTMLParser(max_collect=max_chars * 2 if max_chars else None)
    try:
        parser.feed(value)
        parser.close()
    except StopIteration:
        pass

    text = ''.join(parser.parts).replace('\xa0', ' ')
    clean_text = ' '.join(text.split())
    return Truncator(clean_text).chars(max_chars, truncate='…')
