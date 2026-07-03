import html
import urllib.parse
from copy import copy

import markdown
import nh3
from bs4 import BeautifulSoup
from django import template
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from i18nfield.strings import LazyI18nString
from linkify_it import LinkifyIt
from markdownify import markdownify as html_to_markdown

try:
    from publicsuffixlist import PublicSuffixList

    TLD_SET = sorted({suffix.rsplit('.')[-1] for suffix in PublicSuffixList()._publicsuffix}, reverse=True)
except ImportError:
    from tlds import tld_set

    TLD_SET = sorted(tld_set, key=len, reverse=True)

from eventyay.common.views.redirect import safelink as sl

register = template.Library()

ALLOWED_TAGS = {
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'del', 'div', 'em',
    'hr', 'i', 'li', 'ol', 'strong', 'u', 'ul', 'p', 'pre', 'span', 'table',
    'tbody', 'thead', 'tr', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
}

ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title', 'class'},
    'abbr': {'title'},
    'acronym': {'title'},
    'table': {'width'},
    'td': {'width', 'align'},
    'div': {'class'},
    'p': {'class'},
    'span': {'class', 'title'},
}

ALLOWED_PROTOCOLS = {'http', 'https', 'mailto', 'tel'}

linkifier = LinkifyIt().tlds(TLD_SET)


def process_links(html_content, safelink=True):
    if not html_content:
        return ''
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Linkify text nodes
    for text_node in soup.find_all(string=True):
        parent = text_node.parent
        if parent and parent.name in ['a', 'pre', 'code']:
            continue

        matches = linkifier.match(text_node)
        if matches:
            new_html = ""
            last_idx = 0
            for match in matches:
                new_html += html.escape(text_node[last_idx:match.index])
                url = match.url
                text = match.text
                new_html += f'<a href="{html.escape(url)}">{html.escape(text)}</a>'
                last_idx = match.last_index
            new_html += html.escape(text_node[last_idx:])

            new_soup = BeautifulSoup(new_html, 'html.parser')
            text_node.replace_with(new_soup)

    # 2. Apply safelink and target/rel callbacks
    for a_tag in soup.find_all('a'):
        href = a_tag.get('href')
        if not href:
            continue

        if href.startswith('mailto:') or href.startswith('tel:') or url_has_allowed_host_and_scheme(href, allowed_hosts=None):
            continue

        a_tag['target'] = '_blank'
        a_tag['rel'] = 'noopener'

        if safelink:
            href_unescaped = html.unescape(href)
            a_tag['href'] = sl(href_unescaped)
        else:
            href_unescaped = html.unescape(href)
            a_tag['href'] = urllib.parse.urljoin(settings.SITE_URL, href_unescaped)

    # bs4 adds html/body tags sometimes if the fragment resembles a full doc,
    # but for typical rich text snippets, it should just return the fragment.
    # To be safe, if we only parsed a fragment, soup will output it directly.
    return str(soup)


class CleanerWrapper:
    def __init__(self, tags, attributes, protocols, safelink=True, strip_a=False):
        self.tags = set(tags)
        self.attributes = {k: set(v) for k, v in attributes.items()} if attributes else {}
        self.protocols = set(protocols) if protocols else set()
        self.safelink = safelink
        self.strip_a = strip_a

    def clean(self, html_content):
        sanitized = nh3.clean(
            html_content,
            tags=self.tags,
            attributes=self.attributes,
            url_schemes=self.protocols
        )

        if self.strip_a:
            return sanitized

        return process_links(sanitized, safelink=self.safelink)


CLEANER = CleanerWrapper(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    safelink=True
)

ABSLINK_CLEANER = CleanerWrapper(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    safelink=False
)

NO_LINKS_CLEANER = CleanerWrapper(
    tags=copy(ALLOWED_TAGS) - {'a'},
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    strip_a=True
)

STRIKETHROUGH_RE = '(~{2})(.+?)(~{2})'


def markdown_compile_email(source):
    md_html = markdown.markdown(
        source,
        extensions=[
            'markdown.extensions.sane_lists',
        ],
    )
    sanitized = nh3.clean(
        md_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_PROTOCOLS
    )
    return process_links(sanitized, safelink=False)


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


@register.filter
def rich_text(text: str):
    return render_markdown(text, cleaner=CLEANER)


@register.filter
def rich_text_without_links(text: str):
    return render_markdown(text, cleaner=NO_LINKS_CLEANER)


@register.filter
def rich_text_snippet(text: str):
    return render_markdown(text, cleaner=ABSLINK_CLEANER)


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
