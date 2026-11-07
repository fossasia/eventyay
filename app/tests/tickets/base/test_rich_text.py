import datetime

import pytest

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
            '<p>Entities: &amp; &lt; &gt; &quot; &#39; &nbsp; end</p>',
            'Entities: & < > " \' end',
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
    ],
)
def test_rich_text_to_plain_text(raw, expected):
    assert rich_text_to_plain_text(raw) == expected


def test_rich_text_plain_in_template():
    from django.template import Context, Template

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
    from django.template import Context, Template

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
