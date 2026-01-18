import html
import re
import urllib.parse
from copy import copy

import markdown
import nh3
from django import template
from django.conf import settings
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from markdownify import markdownify as html_to_markdown

try:
    from publicsuffixlist import PublicSuffixList

    TLD_SET = sorted({suffix.rsplit('.')[-1] for suffix in PublicSuffixList()._publicsuffix}, key=len, reverse=True)
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
    'a': {'href', 'title', 'class', 'target'},
    'abbr': {'title'},
    'acronym': {'title'},
    'table': {'width'},
    'td': {'width', 'align'},
    'div': {'class'},
    'p': {'class'},
    'span': {'class', 'title'},
}

ALLOWED_PROTOCOLS = {'http', 'https', 'mailto', 'tel'}

common_tlds = ['com', 'org', 'net', 'edu', 'gov', 'mil', 'int', 'eu', 'us', 'uk', 'ca', 'au', 'de', 'fr', 'it', 'es', 'nl', 'jp', 'kr', 'cn', 'br', 'ru', 'in', 'mx', 'za', 'se', 'no', 'dk', 'fi', 'be', 'ch', 'at', 'pl', 'cz', 'gr', 'pt', 'ie', 'nz', 'sg', 'hk', 'il', 'ar', 'co', 'io', 'info', 'biz', 'name', 'pro', 'mobi', 'tel', 'travel', 'xxx', 'asia']
other_tlds = [tld for tld in TLD_SET if tld not in common_tlds][:250]
tld_pattern = '|'.join(re.escape(tld) for tld in (common_tlds + other_tlds))

# Requires www. or protocol prefix (http://, https://) to prevent false positives with bare domains
URL_RE = re.compile(
    r'(?:(?:https?://)|(?:www\.))'
    r'(?:[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+)'
    r'\.(?:' + tld_pattern + r')'
    r'(?:[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]*)',
    re.IGNORECASE
)
EMAIL_RE = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?:' + tld_pattern + r')\b',
    re.IGNORECASE
)


def linkify_text(text, use_safelink=True):
    """
    Convert plain URLs/emails to links. Only matches http:/https:/www. (not javascript:/data:).
    Uses escape() for safety. Skips text inside existing <a> tags to prevent nesting.
    """

    def replace_url(match):
        url = match.group(0)
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        display_url = match.group(0)
        if use_safelink and not url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            href = sl(html.unescape(url))
            return f'<a href="{href}" target="_blank">{escape(display_url)}</a>'
        elif not use_safelink:
            href = urllib.parse.urljoin(settings.SITE_URL, html.unescape(url))
            return f'<a href="{href}" target="_blank">{escape(display_url)}</a>'
        else:
            return f'<a href="{escape(url)}">{escape(display_url)}</a>'

    def replace_email(match):
        email = match.group(0)
        return f'<a href="mailto:{escape(email)}">{escape(email)}</a>'

    parts = re.split(r'(<a\s[^>]*>.*?</a>)', text, flags=re.IGNORECASE | re.DOTALL)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            part = re.sub(URL_RE, replace_url, part)
            part = re.sub(EMAIL_RE, replace_email, part)
        result.append(part)
    return ''.join(result)


def clean_html(
    text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip_tags=False
):
    """
    Sanitize HTML using nh3. Note: nh3 auto-adds rel="noopener noreferrer" to external links,
    so 'rel' must NOT be in ALLOWED_ATTRIBUTES or it will panic.
    """
    if strip_tags:
        tags = copy(tags) - {'a'}
    return nh3.clean(
        text,
        tags=tags,
        attributes=attributes,
        url_schemes=ALLOWED_PROTOCOLS,
    )


STRIKETHROUGH_RE = '(~{2})(.+?)(~{2})'


def markdown_compile_email(source):
    html_content = markdown.markdown(
        source,
        extensions=[
            'markdown.extensions.sane_lists',
        ],
    )
    cleaned = clean_html(html_content)
    return linkify_text(cleaned, use_safelink=False)


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


def render_markdown(text: str, use_safelink=True, strip_links=False) -> str:
    if not text:
        return ''
    html_content = md.reset().convert(str(text))
    cleaned = clean_html(html_content, strip_tags=strip_links)
    if not strip_links:
        cleaned = linkify_text(cleaned, use_safelink=use_safelink)
    return mark_safe(cleaned)


def render_markdown_abslinks(text: str) -> str:
    return render_markdown(text, use_safelink=False)


@register.filter
def rich_text(text: str, safelinks=True):
    return render_markdown(text, use_safelink=safelinks)


@register.filter
def rich_text_without_links(text: str):
    return render_markdown(text, use_safelink=True, strip_links=True)


@register.filter
def rich_text_snippet(text: str, safelinks=False):
    return render_markdown(text, use_safelink=safelinks)


@register.filter
def html_to_markdown_filter(html_text: str) -> str:
    """Convert HTML to markdown format."""
    return html_text if not html_text else html_to_markdown(html_text)


@register.filter
def append_colon(text: LazyI18nString) -> str:
    text = str(text).strip()
    if not text:
        return ''
    return text if text[-1] in ['.', '!', '?', ':', ';'] else f'{text}:'
