import datetime

import pytest

from eventyay.base.models import Event, Organizer
from eventyay.base.templatetags.rich_text import (
    compile_email_body,
    expand_email_preview_placeholders,
    markdown_compile_email,
    render_markdown_abslinks,
    rich_text_snippet,
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
