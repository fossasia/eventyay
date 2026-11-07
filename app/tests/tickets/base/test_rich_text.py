import datetime

import pytest
from django.template import Context, Template

from eventyay.base.email import get_available_placeholders, get_email_context
from eventyay.base.models import Event, Organizer
from eventyay.base.templatetags.rich_text import (
    compile_email_body,
    expand_email_preview_placeholders,
    markdown_compile_email,
    render_markdown_abslinks,
    rich_text_snippet,
    rich_text_to_plain_text,
)


@pytest.fixture
def event():
    orga = Organizer.objects.create(name='CCC', slug='ccc')
    return Event.objects.create(
        organizer=orga,
        name='30C3',
        slug='30c3',
        date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
        plugins='eventyay.plugins.banktransfer,tests.tickets.testdummy',
    )


@pytest.mark.django_db
def test_expand_email_preview_placeholders_replaces_sample_values(event):
    html = '<p><span data-variable="event_slug" class="tiptap-placeholder-chip">{event_slug}</span></p>'
    result = expand_email_preview_placeholders(html, event)
    assert '{event_slug}' not in result
    assert event.slug in result
    assert 'class="placeholder"' in result


def test_compile_email_body_preserves_html():
    html = '<p><strong>Hello</strong></p>'
    assert compile_email_body(html) == html


def test_compile_email_body_preserves_all_heading_levels():
    from eventyay.base.templatetags.rich_text import _is_tiptap_email_html

    for level in range(1, 7):
        html = f'<h{level}>Heading {level}</h{level}><p>Body</p>'
        assert _is_tiptap_email_html(html)
        assert compile_email_body(html) == html


def test_compile_email_body_compiles_plain_text():
    assert compile_email_body('Hello world') == '<p>Hello world</p>'


def test_compile_email_body_compiles_legacy_inline_html():
    """Legacy Markdown bodies with inline tags must still be compiled."""
    result = compile_email_body('Hello<br>world')
    assert '<p>' in result
    assert 'Hello' in result

    result = compile_email_body('Hello <b>world</b>')
    assert '<p>' in result
    assert 'world' in result


@pytest.mark.django_db
def test_event_name_alias_registered_and_renders(event):
    placeholders = get_available_placeholders(event, ['event'])
    assert 'event' in placeholders
    assert 'event_name' in placeholders
    assert str(placeholders['event_name'].render_sample(event)) == str(event.name)

    ctx = get_email_context(event=event)
    assert str(ctx['event_name']) == str(event.name)
    assert str(ctx['event']) == str(event.name)


@pytest.mark.parametrize(
    'link',
    [
        # Test link detection
        (
            'google.com',
            '<a href="http://google.com" rel="noopener" target="_blank">google.com</a>',
        ),
        # Test abslink_callback
        ('[Call](tel:+12345)', '<a href="tel:+12345" rel="nofollow">Call</a>'),
        (
            '[Foo](/foo)',
            '<a href="/foo" rel="nofollow">Foo</a>',
        ),
        ('mail@example.org', '<a href="mailto:mail@example.org">mail@example.org</a>'),
        # Existing HTML links keep their label text after sanitization
        (
            'evilsite.com',
            '<a href="http://evilsite.com" rel="noopener" target="_blank">evilsite.com</a>',
        ),
        (
            'cool-example.eu',
            '<a href="http://cool-example.eu" rel="noopener" target="_blank">cool-example.eu</a>',
        ),
        (
            '<a href="https://evilsite.com">Evil Site</a>',
            '<a href="https://evilsite.com" rel="noopener" target="_blank">Evil Site</a>',
        ),
        (
            '<a href="https://evilsite.com">evilsite.com</a>',
            '<a href="https://evilsite.com" rel="noopener" target="_blank">evilsite.com</a>',
        ),
        (
            '<a href="https://evilsite.com">goodsite.com</a>',
            '<a href="https://evilsite.com" rel="noopener" target="_blank">goodsite.com</a>',
        ),
        (
            '<a href="https://goodsite.com.evilsite.com">goodsite.com</a>',
            '<a href="https://goodsite.com.evilsite.com" rel="noopener" target="_blank">goodsite.com</a>',
        ),
        (
            '<a href="https://evilsite.com/deep/path">evilsite.com</a>',
            '<a href="https://evilsite.com/deep/path" rel="noopener" target="_blank">evilsite.com</a>',
        ),
    ],
)
def test_linkify_abs(link):
    input, output = link
    assert rich_text_snippet(input) == output
    assert render_markdown_abslinks(input) == f'<p>{output}</p>'
    assert markdown_compile_email(input) == f'<p>{output}</p>'


@pytest.mark.parametrize(
    'raw, expected',
    [
        ('', ''),
        (None, ''),
        ('   ', ''),
        ('<p>Simple paragraph</p>', 'Simple paragraph'),
        ('<p>First</p><p>Second</p>', 'First Second'),
        (
            '<p>Text with <strong>bold</strong> and <em>italic</em>.</p>',
            'Text with bold and italic.',
        ),
        (
            '<p>Visit <a href="https://eventyay.com">Eventyay</a> today!</p>',
            'Visit Eventyay today!',
        ),
        ('Visit [Eventyay](https://eventyay.com) today!', 'Visit Eventyay today!'),
        ('Visit [our site](https://eventyay.com "Title")!', 'Visit our site!'),
        ('<ul><li>Item 1</li><li>Item 2</li></ul>', 'Item 1 Item 2'),
        (
            '<tr><td>Track</td><td>Python</td></tr>',
            'Track Python',
        ),
        (
            '<table><thead><tr><th>Topic</th><th>Speaker</th></tr></thead></table>',
            'Topic Speaker',
        ),
        ('First<br class="line-break">Second', 'First Second'),
        ('Line 1<br style="clear: both;">Line 2<br/>Line 3', 'Line 1 Line 2 Line 3'),
        (
            'Working with vector<T> in C++',
            'Working with vector<T> in C++',
        ),
        (
            'Working with std::vector<int> & List<T>',
            'Working with std::vector<int> & List<T>',
        ),
        (
            'Use Map<String, Object> here',
            'Use Map<String, Object> here',
        ),
        (
            '<div title="a > b">Session text</div>',
            'Session text',
        ),
        (
            '<div title=\'a > b\'>Single quoted text</div>',
            'Single quoted text',
        ),
        (
            '<a href="https://example.com?a=1&b=2" title="x > y">Link</a>',
            'Link',
        ),
        (
            '<custom-widget>Widget content</custom-widget>',
            'Widget content',
        ),
        (
            '<my-session-card class="active">Card content</my-session-card>',
            'Card content',
        ),
        (
            '`vector<T>`',
            'vector<T>',
        ),
        (
            '`<b>code</b>`',
            '<b>code</b>',
        ),
        (
            'Check `x < y and y > z` logic',
            'Check x < y and y > z logic',
        ),
        (
            '<script>alert("xss")</script><p>Clean content</p>',
            'Clean content',
        ),
        (
            '<style>body { color: red; }</style><p>Styled content</p>',
            'Styled content',
        ),
        (
            '<figure><img src="x.jpg"><figcaption>A photo</figcaption></figure>',
            'A photo',
        ),
        (
            '<aside>Sidebar</aside><main>Main content</main>',
            'Sidebar Main content',
        ),
        (
            '<dialog open><p>Modal dialog</p></dialog>',
            'Modal dialog',
        ),
        (
            'Time: <time datetime="2026-11-07">Nov 7</time>',
            'Time: Nov 7',
        ),
        (
            'Press <kbd>Ctrl</kbd> + <kbd>C</kbd>',
            'Press Ctrl + C',
        ),
        (
            '<details><summary>More info</summary>Hidden details</details>',
            'More info Hidden details',
        ),
        (
            '<article><header>Header</header><section>Section</section><footer>Footer</footer></article>',
            'Header Section Footer',
        ),
        ('<blockquote>Quote text</blockquote>', 'Quote text'),
        (
            '<p>Entities: &amp; &lt; &gt; &quot; &#39; &nbsp; end</p>',
            'Entities: & < > " \' end',
        ),
        (
            '&amp;lt;script&amp;gt;',
            '&lt;script&gt;',
        ),
        (
            '   Multiple    spaces   and\nnewlines   ',
            'Multiple spaces and newlines',
        ),
        ('__init__.py', '__init__.py'),
        ('2 ** 8 = 256', '2 ** 8 = 256'),
        ('##general', '##general'),
        ('Text with [square brackets]', 'Text with [square brackets]'),
        (
            '<p>Check out <strong>__init__.py</strong></p>',
            'Check out __init__.py',
        ),
        (
            '**Bold text** and *italic text*',
            'Bold text and italic text',
        ),
        (
            '# Heading 1\n## Heading 2',
            'Heading 1 Heading 2',
        ),
        (
            '**Not bold across\nnew lines**',
            '**Not bold across new lines**',
        ),
        (
            '<p>Unclosed paragraph',
            'Unclosed paragraph',
        ),
    ],
)
def test_rich_text_to_plain_text(raw, expected):
    """Test conversion of rich text / HTML / Markdown to clean plain text."""
    assert rich_text_to_plain_text(raw) == expected


def test_rich_text_bounded_large_plain_text():
    """Verify bounded scanner extracts required text budget from large plain text input."""
    large_input = 'Word ' * 2000  # 10,000 characters
    result = rich_text_to_plain_text(large_input)
    assert len(result) >= 1000
    assert len(result) <= len(large_input)
    assert result.startswith('Word Word')


def test_rich_text_bounded_markup_only_input():
    """Verify bounded scanner does not exhaust budget on markup-only input."""
    markup_only = '<div><span></span></div>' * 2000  # 48,000 characters
    result = rich_text_to_plain_text(markup_only)
    assert result == ''


def test_rich_text_bounded_quote_aware_tag_end():
    """Verify bounded scanner respects quotes containing > characters."""
    raw = '<p title="value > another">' + ('Session ' * 300) + '</p>'
    result = rich_text_to_plain_text(raw)
    assert result.startswith('Session Session')
    assert len(result) >= 1000


def test_rich_text_bounded_huge_attribute_fallback():
    """Verify bounded scanner caps input safely when single attribute exceeds budget."""
    raw = '<div data-info="' + ('x' * 12000) + '">Visible Text</div>'
    result = rich_text_to_plain_text(raw)
    # The opening tag alone exceeds the 10,000 char budget, so scanner safely falls back to text[:10000]
    # and BeautifulSoup extracts what it can without crashing or memory explosion.
    assert isinstance(result, str)


def test_rich_text_plain_in_template():
    """Verify rich_text_plain filter integration within Django templates."""
    template = Template(
        '{% load rich_text %}{{ description|rich_text_plain }}'
    )
    rendered = template.render(
        Context(
            {'description': '<p>Hello <strong>World</strong> &amp; friends!</p>'}
        )
    )
    # In template output, Django auto-escapes plain text characters for HTML attributes/context
    assert rendered == 'Hello World &amp; friends!'


def test_rich_text_plain_truncation_in_template():
    """Verify rich_text_plain piped into truncatechars:200 within Django templates."""
    template = Template(
        '{% load rich_text %}{{ description|rich_text_plain|truncatechars:200 }}'
    )
    # Short description remains unchanged
    short_text = '<p>A short session description.</p>'
    rendered_short = template.render(Context({'description': short_text}))
    assert rendered_short == 'A short session description.'

    # Long description (>200 characters) gets truncated to 200 characters ending with …
    long_raw = '<p>' + 'A' * 250 + '</p>'
    rendered_long = template.render(Context({'description': long_raw}))
    assert len(rendered_long) == 200
    assert rendered_long.endswith('…')
    assert rendered_long == ('A' * 199) + '…'


def test_extremely_long_incomplete_html_tag():
    """Verify extremely long incomplete HTML tags do not cause worker hangs or crashes."""
    raw = '<div class="' + ('very-long-attribute-value-' * 2000)
    result = rich_text_to_plain_text(raw)
    assert isinstance(result, str)


def test_repeated_tag_starts_linear_performance():
    """Verify repeated tag starts without closing brackets complete in bounded time without quadratic backtracking."""
    import time
    raw = '<a ' * 20000  # 60,000 characters of unclosed tag starts
    start = time.perf_counter()
    result = rich_text_to_plain_text(raw)
    elapsed = time.perf_counter() - start
    assert isinstance(result, str)
    # 60,000 chars should take well under 1 second with linear scanning (<0.05s typical)
    assert elapsed < 2.0


def test_repeated_less_than_characters():
    """Verify repeated '<' characters are processed safely in linear time."""
    raw = '<' * 20000
    result = rich_text_to_plain_text(raw)
    assert isinstance(result, str)


def test_long_quoted_attributes_with_greater_than():
    """Verify long quoted attributes containing '>' do not break tag parsing."""
    attr_val = 'condition > 0 and value > 100 ' * 100
    raw = f'<span data-expr="{attr_val}" title="formula > 5">Calculated Result</span>'
    result = rich_text_to_plain_text(raw)
    assert result == 'Calculated Result'


def test_markdown_link_near_truncation_boundary():
    """Verify Markdown links crossing or near the truncation budget boundary are preserved without cutting."""
    prefix = 'Word ' * 195  # ~975 characters
    link = '[Special Keynote Session](https://eventyay.com/keynote)'
    suffix = ' Extra ' * 1000  # Pushes total length past trigger bound
    raw = f'{prefix}{link}{suffix}'
    result = rich_text_to_plain_text(raw)
    assert 'Special Keynote Session' in result
    assert '[' not in result
    assert '](http' not in result


def test_inline_code_and_generics_near_truncation_boundary():
    """Verify inline code spans and technical generics near the boundary are preserved cleanly."""
    prefix = 'Overview ' * 105  # ~945 characters
    code_span = '`std::vector<int>`'
    generic = 'Map<String, Object>'
    suffix = ' Trailing details ' * 500
    raw = f'{prefix}{code_span} and {generic}{suffix}'
    result = rich_text_to_plain_text(raw)
    assert 'std::vector<int>' in result
    assert 'Map<String, Object>' in result


def test_emphasis_near_truncation_boundary():
    """Verify Markdown bold and italic near the truncation boundary are not severed in half."""
    prefix = 'Section ' * 120  # ~960 characters
    bold = '**Crucial Announcement**'
    suffix = ' More description ' * 500
    raw = f'{prefix}{bold}{suffix}'
    result = rich_text_to_plain_text(raw)
    assert 'Crucial Announcement' in result
    assert '**' not in result


def test_unclosed_long_markdown_link_near_boundary():
    """Verify very long malformed Markdown link with no closing delimiter is safely bounded and cleanly cut."""
    prefix = 'Summary ' * 120  # ~960 characters
    unclosed_link = '[Unclosed Malformed Link](https://example.com/very/long/path/' + ('x' * 50000)
    raw = f'{prefix}{unclosed_link}'
    result = rich_text_to_plain_text(raw)
    assert 'Summary' in result
    assert '[' not in result
    assert '](http' not in result
    assert 'x' * 100 not in result
    assert len(result) <= 10000

    # Also verify unclosed link without preceding text does not leave broken link syntax
    raw_no_prefix = unclosed_link
    result_no_prefix = rich_text_to_plain_text(raw_no_prefix)
    assert '[' not in result_no_prefix
    assert '](http' not in result_no_prefix
    assert 'x' * 100 not in result_no_prefix
