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

_TIPTAP_BLOCK_START_RE = re.compile(
    r'^\s*<(p|ul|ol|blockquote)(\s|>)',
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


def expand_email_preview_placeholders(html: str, event, *, locale: str | None = None) -> str:
    """Replace ``{placeholder}`` tokens with sample values for editor preview.

    Uses the same sample rendering as the Message center's full-form preview so
    the toolbar preview matches what users see after clicking "Preview email".
    """
    from django.utils.translation import gettext

    from eventyay.base.email import get_available_placeholders
    from eventyay.base.i18n import language
    from eventyay.base.services.mail import TolerantDict

    resolved_locale = locale or event.settings.locale
    if resolved_locale not in event.settings.locales:
        resolved_locale = event.settings.locale

    with language(resolved_locale, event.settings.region):
        context_dict = TolerantDict()
        for key, placeholder in get_available_placeholders(
            event, list(_PREVIEW_PLACEHOLDER_CONTEXT)
        ).items():
            context_dict[key] = (
                '<span class="placeholder" title="{}">{}</span>'.format(
                    gettext('This value will be replaced based on dynamic parameters.'),
                    placeholder.render_sample(event),
                )
            )
        return html.format_map(context_dict)


def compile_email_body(source: str) -> str:
    """Render an email body fragment as HTML.

    Plain-text and legacy Markdown bodies are compiled with
    ``markdown_compile_email``.  Content that is already HTML (for example from
    the Tiptap email editor) is returned unchanged.
    """
    if not source:
        return source
    if _is_tiptap_email_html(source):
        return source
    return markdown_compile_email(source)


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
