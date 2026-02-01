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
from django import template
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from markdownify import markdownify as html_to_markdown

try:
    from bleach.css_sanitizer import CSSSanitizer
except ImportError:  # pragma: no cover
    CSSSanitizer = None

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
    'ul',
    'p',
    'pre',
    'span',
    'sub',
    'sup',
    'table',
    'tbody',
    'tfoot',
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
    'a': ['href', 'title', 'class', 'rel', 'target'],
    'abbr': ['title'],
    'acronym': ['title'],
    'code': ['class'],
    'pre': ['class'],
    'table': ['width'],
    'td': ['width', 'align', 'colspan', 'rowspan'],
    'th': ['width', 'align', 'colspan', 'rowspan'],
    'div': ['class'],
    'p': ['class'],
    'span': ['class', 'title'],
}

# TinyMCE uses inline styles for color/background and text decoration.
_STYLE_TAGS = ('div', 'p', 'span')
for _tag in _STYLE_TAGS:
    ALLOWED_ATTRIBUTES.setdefault(_tag, []).append('style')

ALLOWED_PROTOCOLS = {'http', 'https', 'mailto', 'tel'}

# TODO: Remove bleach library
URL_RE = build_url_re(tlds=TLD_SET)
EMAIL_RE = build_email_re(tlds=TLD_SET)


_HTML_TAG_RE = re.compile(r'<\s*/?\s*[a-z][^>]*>', re.IGNORECASE)


def looks_like_html(text: str) -> bool:
    """Heuristically determine whether the given text should be treated as HTML.

    This check is intentionally conservative to avoid misclassifying plain text
    (including code snippets) as HTML, which would bypass Markdown processing.
    """
    if not text:
        return False

    matches = list(_HTML_TAG_RE.finditer(text))
    if not matches:
        return False

    # Multiple tag-like patterns strongly suggests HTML.
    if len(matches) > 1:
        return True

    # With only a single tag, be stricter: require it to be at the start or end
    # of the non-whitespace content.
    stripped = text.strip()
    if not stripped:
        return False
    first_content_index = text.find(stripped)
    last_content_index = first_content_index + len(stripped)
    match = matches[0]
    return match.start() == first_content_index or match.end() == last_content_index


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
CLEANER_KWARGS = {}
if CSSSanitizer:
    CLEANER_KWARGS['css_sanitizer'] = CSSSanitizer(
        allowed_css_properties=['color', 'background-color', 'text-decoration'],
    )

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
    **CLEANER_KWARGS,
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
    **CLEANER_KWARGS,
)

# TODO: Implement nh3 equivalent
NO_LINKS_CLEANER = bleach.Cleaner(
    tags=copy(ALLOWED_TAGS) - {'a'},
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    strip=True,
    **CLEANER_KWARGS,
)

STRIKETHROUGH_RE = '(~{2})(.+?)(~{2})'

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
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            protocols=ALLOWED_PROTOCOLS,
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


def render_markdown(text: str, cleaner=CLEANER) -> str:
    if not text:
        return ''
    text = str(text)
    if looks_like_html(text):
        return mark_safe(cleaner.clean(text))
    return mark_safe(cleaner.clean(md.reset().convert(text)))


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
