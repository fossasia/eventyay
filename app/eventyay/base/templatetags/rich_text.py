import html
import re
import urllib.parse
from copy import copy
from functools import partial

# TODO: Remove bleach import
import bleach
import markdown
# TODO: Remove bleach import
from bleach import DEFAULT_CALLBACKS
# TODO: Remove bleach import
from bleach.linkifier import build_email_re, build_url_re
from bs4 import BeautifulSoup
from django import template
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from markdownify import markdownify as html_to_markdown

try:
    from publicsuffixlist import PublicSuffixList

    TLD_SET = sorted({suffix.rsplit('.')[-1] for suffix in PublicSuffixList()._publicsuffix}, reverse=True)
except ImportError:
    from tlds import tld_set

    TLD_SET = sorted(tld_set, key=len, reverse=True)

from i18nfield.strings import LazyI18nString

from eventyay.common.views.redirect import safelink as sl

register = template.Library()

ALLOWED_TAGS = {
    'a',
    'abbr',
    'acronym',
    'b',
    'blockquote',
    'br',
    'code',
    'del',
    'div',
    'em',
    'hr',
    'i',
    'li',
    'ol',
    'strong',
    'u',
    'ul',
    'p',
    'pre',
    'span',
    'table',
    'tbody',
    'thead',
    'tr',
    'td',
    'th',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
}

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'class'],
    'abbr': ['title'],
    'acronym': ['title'],
    'table': ['width'],
    'td': ['width', 'align'],
    'div': ['class'],
    'p': ['class'],
    'span': ['class', 'title'],
}

ALLOWED_PROTOCOLS = {'http', 'https', 'mailto', 'tel'}

# TODO: Remove bleach library
URL_RE = build_url_re(tlds=TLD_SET)
EMAIL_RE = build_email_re(tlds=TLD_SET)


def link_callback(attrs, is_new, safelink=True):
    url = attrs.get((None, 'href'), '/')
    if url.startswith('mailto:') or url.startswith('tel:') or url_has_allowed_host_and_scheme(url, allowed_hosts=None):
        return attrs
    attrs[None, 'target'] = '_blank'
    attrs[None, 'rel'] = 'noopener'
    if safelink:
        url = html.unescape(url)
        attrs[None, 'href'] = sl(url)
    else:
        url = html.unescape(url)
        attrs[None, 'href'] = urllib.parse.urljoin(settings.SITE_URL, url)
    return attrs


safelink_callback = partial(link_callback, safelink=True)
abslink_callback = partial(link_callback, safelink=False)

# TODO: Implement nh3 equivalent
CLEANER = bleach.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    filters=[
        partial(
            bleach.linkifier.LinkifyFilter,
            url_re=URL_RE,
            parse_email=True,
            email_re=EMAIL_RE,
            skip_tags={'pre', 'code'},
            callbacks=DEFAULT_CALLBACKS + [safelink_callback],
        )
    ],
)

# TODO: Implement nh3 equivalent
ABSLINK_CLEANER = bleach.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    filters=[
        partial(
            bleach.linkifier.LinkifyFilter,
            url_re=URL_RE,
            parse_email=True,
            email_re=EMAIL_RE,
            skip_tags={'pre', 'code'},
            callbacks=DEFAULT_CALLBACKS + [abslink_callback],
        )
    ],
)

# TODO: Implement nh3 equivalent
NO_LINKS_CLEANER = bleach.Cleaner(
    tags=copy(ALLOWED_TAGS) - {'a'},
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    strip=True,
)

STRIKETHROUGH_RE = '(~{2})(.+?)(~{2})'

# Email bodies may include trusted placeholder HTML such as QR ``<img>`` tags
# (data-URI PNGs) and CTA buttons. Keep these allowlists scoped to email
# compilation so public rich-text rendering stays stricter.
EMAIL_ALLOWED_TAGS = ALLOWED_TAGS | {'img'}
EMAIL_ALLOWED_ATTRIBUTES = {
    **ALLOWED_ATTRIBUTES,
    'img': ['src', 'alt', 'width', 'height'],
}
# ``data`` is allowed only so QR ``<img src="data:image/...">`` survives. Anchor
# ``href`` values that use ``data:`` are rejected in ``email_allowed_attributes``.
EMAIL_ALLOWED_PROTOCOLS = ALLOWED_PROTOCOLS | {'data'}

_TIPTAP_BLOCK_START_RE = re.compile(
    r'^\s*<(p|ul|ol|blockquote|h[1-6])(\s|>)',
    re.IGNORECASE | re.DOTALL,
)


def _is_tiptap_email_html(source: str) -> bool:
    """Return True when *source* looks like HTML from the Tiptap email editor.

    ``nh3.is_html()`` is too broad: legacy Markdown bodies may contain inline
    tags such as ``<br>`` or ``<b>`` and must still be compiled.  Tiptap
    output is always block-structured (``<p>``, lists, blockquote) or contains
    placeholder chips with ``data-variable``.
    """
    if not source:
        return False
    source = str(source)
    if 'data-variable=' in source:
        return True
    return bool(_TIPTAP_BLOCK_START_RE.match(source))


_PREVIEW_PLACEHOLDER_CONTEXT: tuple[str, ...] = (
    'event',
    'order',
    'position',
    'position_or_address',
    'team',
    'invoice_address',
)


# Query value the bulk-voucher form adds to the shared preview URL.
VOUCHER_EMAIL_PREVIEW_CONTEXT = 'voucher'

_VOUCHER_PREVIEW_PARAMETERS: tuple[str, ...] = ('event', 'voucher_list', 'name')


def _preview_placeholder_context(html_body: str) -> list[str]:
    """Base preview context, plus voucher placeholders when the body uses them.

    Voucher placeholders are added only for bodies that reference them so the
    voucher ``{url}`` sample does not replace the order status ``{url}``.
    A body that contains only ``{url}`` stays on the order context. Bulk-voucher
    previews pass ``preview_context`` instead of widening this check.
    """
    parameters = list(_PREVIEW_PLACEHOLDER_CONTEXT)
    if re.search(
        r'\{voucher_(?:list|url)\}|data-variable=["\']voucher_(?:list|url)["\']',
        html_body or '',
    ):
        parameters.extend(['voucher_list', 'name'])
    return parameters


def _preview_parameters(html_body: str, preview_context: str | None) -> list[str]:
    """Placeholder groups for one preview request.

    ``voucher`` is the bulk-voucher form. It always includes ``voucher_list``,
    so ``{url}`` samples the event shop the same way delivery does.
    """
    if preview_context == VOUCHER_EMAIL_PREVIEW_CONTEXT:
        return list(_VOUCHER_PREVIEW_PARAMETERS)
    return _preview_placeholder_context(html_body)


def expand_email_preview_placeholders(
    html_body: str,
    event,
    *,
    locale: str | None = None,
    preview_context: str | None = None,
) -> str:
    """Replace ``{placeholder}`` tokens / Tiptap chips with sample values for editor preview."""
    from eventyay.base.i18n import language
    from eventyay.base.services.mail import expand_email_variable_chips

    resolved_locale = locale or event.settings.locale
    if resolved_locale not in event.settings.locales:
        resolved_locale = event.settings.locale

    with language(resolved_locale, event.settings.region):
        context_dict = build_email_preview_context(event, _preview_parameters(html_body, preview_context))
        expanded = html_body.format_map(context_dict)
        return expand_email_variable_chips(expanded, dict(context_dict))


def compile_email_body(source: str) -> str:
    """Render an email body fragment as HTML.

    Plain-text and legacy Markdown bodies are compiled with
    ``markdown_compile_email``.  Content that is already HTML (for example from
    the Tiptap email editor) is sanitized and returned.
    """
    if not source:
        return source
    source = str(source)
    if _is_tiptap_email_html(source):
        from eventyay.common.sanitizers import sanitize_email_html
        return sanitize_email_html(source)
    return markdown_compile_email(source)


def email_allowed_attributes(tag: str, name: str, value: str) -> bool:
    """Allowlist email HTML attributes; forbid ``data:`` links on anchors."""
    allowed_for_tag = EMAIL_ALLOWED_ATTRIBUTES.get(tag)
    if not allowed_for_tag or name not in allowed_for_tag:
        return False
    if tag == 'a' and name == 'href' and value.lstrip().lower().startswith('data:'):
        return False
    if tag == 'img' and name == 'src':
        normalized = value.lstrip().lower()
        return normalized.startswith(('data:image/', 'http://', 'https://', '/'))
    return True


def is_placeholder_html_sample(sample: str) -> bool:
    """Return True when a placeholder sample is trusted HTML (button, QR image)."""
    stripped = str(sample).lstrip()
    return stripped.startswith('<') and not stripped.startswith('</')


def build_email_preview_context(event, base_parameters: list[str]):
    """Build sendmail preview context, keeping HTML placeholder samples intact."""
    from django.utils.translation import gettext

    from eventyay.base.email import get_available_placeholders as get_base_placeholders
    from eventyay.mail.context import get_available_placeholders as get_talk_placeholders
    from eventyay.base.services.mail import TolerantDict

    context_dict = TolerantDict()
    title = html.escape(str(gettext('This value will be replaced based on dynamic parameters.')))
    
    # Get placeholders from base module
    base_placeholders = get_base_placeholders(event, list(base_parameters))
    
    # Get placeholders from talk module
    talk_placeholders = get_talk_placeholders(event, list(base_parameters))
        
    all_placeholders = {**base_placeholders, **talk_placeholders}

    for key, placeholder in all_placeholders.items():
        sample = str(placeholder.render_sample(event))
        if is_placeholder_html_sample(sample):
            context_dict[key] = sample
        else:
            context_dict[key] = f'<span class="placeholder" title="{title}">{html.escape(sample)}</span>'
    return context_dict


# TODO: Implement nh3 equivalent
def markdown_compile_email(source):
    linker = bleach.Linker(
        url_re=URL_RE,
        email_re=EMAIL_RE,
        callbacks=DEFAULT_CALLBACKS + [abslink_callback],
        parse_email=True,
    )
    return linker.linkify(
        bleach.clean(
            markdown.markdown(
                source,
                extensions=[
                    'markdown.extensions.sane_lists',
                    #  'markdown.extensions.nl2br' # disabled for backwards-compatibility
                ],
            ),
            tags=EMAIL_ALLOWED_TAGS,
            attributes=email_allowed_attributes,
            protocols=EMAIL_ALLOWED_PROTOCOLS,
        )
    )


class StrikeThroughExtension(markdown.Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            markdown.inlinepatterns.SimpleTagPattern(STRIKETHROUGH_RE, 'del'),
            'strikethrough',
            200,
        )


md = markdown.Markdown(
    extensions=[
        'markdown.extensions.nl2br',
        'markdown.extensions.sane_lists',
        'markdown.extensions.tables',
        'markdown.extensions.fenced_code',
        'markdown.extensions.codehilite',
        'markdown.extensions.md_in_html',
        StrikeThroughExtension(),
    ]
)


def compile_markdown(text: str) -> str:
    if not text:
        return ''
    return md.reset().convert(str(text))


def render_markdown(text: str, cleaner=CLEANER) -> str:
    if not text:
        return ''
    body_md = cleaner.clean(compile_markdown(text))
    return mark_safe(body_md)


def render_markdown_abslinks(text: str) -> str:
    return render_markdown(text, cleaner=ABSLINK_CLEANER)


def _unwrap_single_paragraph(html: str) -> str:
    """Return inline HTML for snippet contexts by removing one outer <p> wrapper."""
    match = re.fullmatch(r'<p>(.*)</p>\s*', html, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    return html


@register.filter
def rich_text(text: str):
    return render_markdown(text, cleaner=CLEANER)


@register.filter
def rich_text_without_links(text: str):
    return render_markdown(text, cleaner=NO_LINKS_CLEANER)


@register.filter
def rich_text_snippet(text: str):
    rendered = render_markdown(text, cleaner=ABSLINK_CLEANER)
    if not rendered:
        return rendered
    return mark_safe(_unwrap_single_paragraph(str(rendered)))


def _link_remote_images(html_body: str) -> str:
    """Replace images that are not embedded in the email with links, so viewing it loads nothing."""
    soup = BeautifulSoup(html_body, 'html.parser')
    for img in soup.find_all('img'):
        src = img.get('src', '').strip()
        # Browsers ignore whitespace and control characters in URLs, so check the source without them.
        if re.sub(r'[\x00-\x20]', '', src).lower().startswith('data:image/'):
            continue
        if src:
            link = soup.new_tag('a', href=src, target='_blank', rel='noopener noreferrer')
            link.string = img.get('alt') or src
            img.replace_with(link)
        else:
            img.replace_with(img.get('alt', ''))
    return str(soup)


@register.filter
def rich_text_email(text: str):
    """Render a stored email body the way the HTML email shows it to the recipient.

    Images that are not embedded in the email are shown as links instead, so opening
    the email history does not contact the image host.
    """
    if not text:
        return ''
    return mark_safe(_link_remote_images(compile_email_body(text)))


@register.filter
def html_to_markdown_filter(html_text: str) -> str:
    """Convert HTML to markdown format."""
    return html_text if not html_text else html_to_markdown(html_text)


_HTML5_TAGS = frozenset({
    'a',
    'abbr',
    'address',
    'area',
    'article',
    'aside',
    'audio',
    'b',
    'base',
    'bdi',
    'bdo',
    'blockquote',
    'body',
    'br',
    'button',
    'canvas',
    'caption',
    'cite',
    'code',
    'col',
    'colgroup',
    'data',
    'datalist',
    'dd',
    'del',
    'details',
    'dfn',
    'dialog',
    'div',
    'dl',
    'dt',
    'em',
    'embed',
    'fieldset',
    'figcaption',
    'figure',
    'footer',
    'form',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'head',
    'header',
    'hgroup',
    'hr',
    'html',
    'i',
    'iframe',
    'img',
    'input',
    'ins',
    'kbd',
    'label',
    'legend',
    'li',
    'link',
    'main',
    'map',
    'mark',
    'menu',
    'meta',
    'meter',
    'nav',
    'noscript',
    'object',
    'ol',
    'optgroup',
    'option',
    'output',
    'p',
    'picture',
    'portal',
    'pre',
    'progress',
    'q',
    'rp',
    'rt',
    'ruby',
    's',
    'samp',
    'script',
    'search',
    'section',
    'select',
    'slot',
    'small',
    'source',
    'span',
    'strong',
    'style',
    'sub',
    'summary',
    'sup',
    'svg',
    'table',
    'tbody',
    'td',
    'template',
    'textarea',
    'tfoot',
    'th',
    'thead',
    'time',
    'title',
    'tr',
    'track',
    'u',
    'ul',
    'var',
    'video',
    'wbr',
})

_BLOCK_TAGS = frozenset({
    'address',
    'article',
    'aside',
    'blockquote',
    'dd',
    'details',
    'div',
    'dl',
    'dt',
    'fieldset',
    'figcaption',
    'figure',
    'footer',
    'form',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'header',
    'hr',
    'li',
    'main',
    'nav',
    'ol',
    'p',
    'pre',
    'section',
    'summary',
    'table',
    'tbody',
    'td',
    'th',
    'thead',
    'tr',
    'ul',
})

# Code spans: inline backticks
_CODE_SPAN_RE = re.compile(r'`([^`\n]+)`')

# Markdown links: [label](url)
_MARKDOWN_LINK_RE = re.compile(
    r'\[([^\]\n]+)\]\((?:[^\s)]+)(?:\s+["\'][^"\']*["\']\s*)?\)'
)

# Markdown headings: 1-6 hashes at line start followed by whitespace
_MARKDOWN_HEADING_RE = re.compile(r'(?m)^[ \t]*#{1,6}[ \t]+')

# Markdown bold: strictly single-line, non-space adjacent to delimiters
_MARKDOWN_BOLD_RE = re.compile(
    r'(?<![a-zA-Z0-9*])\*\*([^\s*\n](?:[^\n*]*?[^\s*\n])?)\*\*(?![a-zA-Z0-9*])'
)

# Markdown italic: strictly single-line, non-space adjacent to delimiters
_MARKDOWN_ITALIC_RE = re.compile(
    r'(?<![a-zA-Z0-9*])\*([^\s*\n](?:[^\n*]*?[^\s*\n])?)\*(?![a-zA-Z0-9*])'
)

# Markdown strikethrough: strictly single-line
_MARKDOWN_STRIKE_RE = re.compile(r'~~([^~\n]+)~~')

_MAX_PREVIEW_INPUT_CHARS = 10000
_TRIGGER_BOUND_LEN = 4000
_TARGET_TEXT_LEN = 1000


def is_html_tag_name(name: str) -> bool:
    """Return True if `name` matches a standard HTML5 element or a valid W3C custom element."""
    name_lower = name.lower()
    return name_lower in _HTML5_TAGS or ('-' in name_lower and name_lower[0].isalpha())


def _escape_non_html_tags(text: str) -> str:
    """Escape angle brackets that do not form recognized HTML5 or custom tags, respecting quoted attributes.

    Uses a single-pass linear-time scanner that avoids regex backtracking on malformed or incomplete tags.
    """
    n = len(text)
    if n == 0:
        return ''
    out: list[str] = []
    i = 0
    while i < n:
        ch = text[i]
        if ch != '<':
            out.append(ch)
            i += 1
            continue

        name_start = i + 1
        if name_start < n and text[name_start] == '/':
            name_start += 1

        if name_start >= n or not text[name_start].isalpha():
            out.append(ch)
            i += 1
            continue

        name_end = name_start + 1
        while name_end < n and (text[name_end].isalnum() or text[name_end] in '_-'):
            name_end += 1

        name = text[name_start:name_end]

        quote_char = None
        tag_closed = False
        j = name_end
        while j < n:
            c = text[j]
            if quote_char is not None:
                if c == quote_char:
                    quote_char = None
            elif c in ('"', "'"):
                quote_char = c
            elif c == '>':
                tag_closed = True
                break
            elif c == '<':
                # An unquoted '<' indicates an unclosed tag prefix; abort this candidate
                break
            j += 1

        if tag_closed and quote_char is None:
            after_name = text[name_end:j]
            if is_html_tag_name(name) and (not after_name or after_name[0] in ' \t\r\n/'):
                out.append(text[i:j + 1])
            else:
                inner = text[i + 1:j]
                out.append(f'&lt;{inner}&gt;')
            i = j + 1
        else:
            out.append(text[i:j])
            i = j

    return ''.join(out)


def _find_next_tag_end(text: str, start: int, limit: int | None = None) -> int:
    """Find the index of the next closing '>' character outside of attribute quotes."""
    quote_char = None
    n = len(text) if limit is None else min(len(text), limit)
    for idx in range(start, n):
        ch = text[idx]
        if quote_char is not None:
            if ch == quote_char:
                quote_char = None
        elif ch in ('"', "'"):
            quote_char = ch
        elif ch == '>':
            return idx
    return -1


def _bound_input_for_preview(
    text: str,
    target_text_len: int = _TARGET_TEXT_LEN,
    trigger_len: int = _TRIGGER_BOUND_LEN,
    max_budget: int = _MAX_PREVIEW_INPUT_CHARS,
) -> str:
    """Bound preview processing BEFORE regex matching, preserving Markdown & HTML constructs.

    Only activates when `len(text) > trigger_len`. Scans for at least `target_text_len`
    plain text characters while properly tracking quote states in attributes and completing
    open Markdown constructs (links, code spans, emphasis) before cutting off. Caps the
    maximum returned string at `max_budget` (10,000 characters). Note that any text
    appearing past a 10,000-character attribute or markup prefix is intentionally discarded
    to protect against denial of service and memory bloat.
    """
    if len(text) <= trigger_len:
        return text[:max_budget]

    text_chars = 0
    in_tag = False
    quote_char = None
    i = 0
    limit = min(len(text), max_budget)

    while i < limit:
        ch = text[i]

        if not in_tag:
            if ch == '<':
                if i + 1 < limit and (text[i + 1].isalpha() or text[i + 1] in ('/', '!')):
                    in_tag = True
                    quote_char = None
                    i += 1
                    continue
                else:
                    text_chars += 1
            else:
                text_chars += 1

            if text_chars >= target_text_len:
                cutoff = i + 1

                # Check for open Markdown constructs on the current line
                line_start = text.rfind('\n', 0, cutoff)
                line_start = 0 if line_start == -1 else line_start + 1
                current_line_prefix = text[line_start:cutoff]
                rolled_back = False

                # 1. Check if inside a Markdown link: [label](url)
                last_open_bracket = current_line_prefix.rfind('[')
                if last_open_bracket != -1:
                    bracket_pos = line_start + last_open_bracket
                    # Bound regex matching strictly to avoid scanning beyond budget
                    max_link_window = min(cutoff + 500, max_budget)
                    link_match = (
                        _MARKDOWN_LINK_RE.match(text[bracket_pos:max_link_window])
                        if max_link_window > bracket_pos
                        else None
                    )
                    if link_match:
                        link_end = bracket_pos + link_match.end()
                        if link_end > cutoff:
                            cutoff = link_end
                    else:
                        close_bracket = current_line_prefix.find(']', last_open_bracket)
                        is_broken_link = (
                            close_bracket == -1
                            or text[line_start + close_bracket + 1 : line_start + close_bracket + 2] == '('
                        )
                        if is_broken_link:
                            cutoff = bracket_pos
                            rolled_back = True

                # 2. Check if inside an inline code span
                backtick_count = current_line_prefix.count('`')
                if backtick_count % 2 == 1:
                    max_code_window = min(cutoff + 200, max_budget)
                    next_backtick = text.find('`', cutoff, max_code_window)
                    next_newline = text.find('\n', cutoff, max_code_window)
                    if (
                        next_backtick != -1
                        and (next_newline == -1 or next_backtick < next_newline)
                    ):
                        cutoff = next_backtick + 1
                    else:
                        last_tick = text.rfind('`', line_start, cutoff)
                        if last_tick > 0:
                            cutoff = last_tick
                            rolled_back = True

                # 3. Check if inside emphasis/strikethrough (**bold**, ~~strike~~, *italic*)
                for delim in ('**', '~~', '*'):
                    delim_count = current_line_prefix.count(delim)
                    if delim_count % 2 == 1:
                        max_delim_window = min(cutoff + 200, max_budget)
                        next_delim = text.find(delim, cutoff, max_delim_window)
                        next_newline = text.find('\n', cutoff, max_delim_window)
                        if (
                            next_delim != -1
                            and (next_newline == -1 or next_delim < next_newline)
                        ):
                            cutoff = next_delim + len(delim)
                        else:
                            last_delim = text.rfind(delim, line_start, cutoff)
                            if last_delim > 0:
                                cutoff = last_delim
                                rolled_back = True
                        break

                # 4. Check if inside an HTML tag
                # Single-pass linear backward scan to find the last candidate HTML tag opener:
                # matches the scanner requirement that the following char is alpha, '/', or '!'.
                last_tag_lt = -1
                for idx in range(cutoff - 1, -1, -1):
                    if text[idx] == '<' and idx + 1 < len(text) and (
                        text[idx + 1].isalpha() or text[idx + 1] in ('/', '!')
                    ):
                        last_tag_lt = idx
                        break

                if last_tag_lt != -1:
                    tag_end = _find_next_tag_end(text, last_tag_lt, max_budget)
                    if tag_end != -1:
                        if tag_end >= cutoff:
                            cutoff = tag_end + 1
                    elif last_tag_lt > 0:
                        cutoff = last_tag_lt
                        rolled_back = True

                # 5. Advance to next word/tag boundary if safe
                if not rolled_back and cutoff < limit:
                    for adv in range(cutoff, min(cutoff + 40, limit)):
                        if text[adv] in (' ', '\t', '\n', '<'):
                            cutoff = adv
                            break

                return text[:min(cutoff, max_budget)]

        else:
            if quote_char is not None:
                if ch == quote_char:
                    quote_char = None
            elif ch in ('"', "'"):
                quote_char = ch
            elif ch == '>':
                in_tag = False
            elif ch == '<':
                # An unquoted '<' starts a new candidate tag
                in_tag = i + 1 < limit and (text[i + 1].isalpha() or text[i + 1] in ('/', '!'))

        i += 1

    return text[:max_budget]


def _bound_html_for_preview(
    text: str,
    target_text_len: int = _TARGET_TEXT_LEN,
    trigger_len: int = _TRIGGER_BOUND_LEN,
    max_budget: int = _MAX_PREVIEW_INPUT_CHARS,
) -> str:
    """Backwards-compatible wrapper for `_bound_input_for_preview`."""
    return _bound_input_for_preview(text, target_text_len, trigger_len, max_budget)


def rich_text_to_plain_text(text: str) -> str:
    """Convert rich text (HTML/Markdown) to single-line plain text for metadata previews.

    Strips HTML tags, unwraps Markdown links, headings, bold, italic, and strikethrough,
    preserves technical notation like ``vector<T>`` and literal code spans, decomposes
    ``<script>`` and ``<style>`` blocks, and normalizes all whitespace.
    """
    if not text:
        return ''

    # 1. Bound exceptionally large inputs BEFORE regex matching to protect CPU and memory
    raw = _bound_input_for_preview(str(text))

    # 2. Protect inline code spans so literal tags like `<p>` are not eaten by the HTML parser
    raw = _CODE_SPAN_RE.sub(lambda m: html.escape(m.group(1)), raw)

    # 3. Convert Markdown links [label](url) to their label text
    raw = _MARKDOWN_LINK_RE.sub(r'\1', raw)

    # 4. Unwrap targeted Markdown formatting within single-line boundaries
    raw = _MARKDOWN_HEADING_RE.sub('', raw)
    raw = _MARKDOWN_BOLD_RE.sub(r'\1', raw)
    raw = _MARKDOWN_ITALIC_RE.sub(r'\1', raw)
    raw = _MARKDOWN_STRIKE_RE.sub(r'\1', raw)

    # 5. Escape non-HTML angle brackets (e.g. vector<T>) using linear-time scanner
    raw = _escape_non_html_tags(raw)

    soup = BeautifulSoup(raw, 'html.parser')

    # Remove script and style elements completely
    for tag in soup.find_all(['script', 'style']):
        tag.decompose()

    # Convert br tags to spaces
    for br in soup.find_all('br'):
        br.replace_with(' ')

    # Insert spaces around block elements
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.append(' ')

    # BeautifulSoup naturally decodes all standard HTML entities (&amp;, &lt;, &gt;, &quot;, &#39;)
    plain = soup.get_text()
    plain = plain.replace('\xa0', ' ')
    return ' '.join(plain.split())


@register.filter
def rich_text_plain(text: str) -> str:
    """Template filter converting rich text into single-line plain text for metadata descriptions."""
    return rich_text_to_plain_text(text)


@register.filter
def append_colon(text: LazyI18nString) -> str:
    text = str(text).strip()
    if not text:
        return ''
    return text if text[-1] in ['.', '!', '?', ':', ';'] else f'{text}:'
