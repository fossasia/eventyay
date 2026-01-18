import pytest

from eventyay.base.templatetags.rich_text import (
    clean_html,
    linkify_text,
    markdown_compile_email,
    rich_text,
    rich_text_snippet,
)


@pytest.mark.parametrize(
    'input_text,expected_check',
    [
        (
            'www.google.com',
            lambda result: '<a href=' in result and 'google.com' in result
        ),
        (
            '[Call](tel:+12345)',
            lambda result: 'href="tel:+12345"' in result and '>Call</a>' in result
        ),
        (
            '[Foo](/foo)',
            lambda result: 'href="/foo"' in result and '>Foo</a>' in result
        ),
        (
            'mail@example.org',
            lambda result: 'href="mailto:mail@example.org"' in result
        ),
        (
            'www.evilsite.com',
            lambda result: '<a href=' in result and 'evilsite.com' in result
        ),
        (
            'www.cool-example.eu',
            lambda result: '<a href=' in result and 'cool-example.eu' in result
        ),
        (
            '<a href="https://evilsite.com">Evil Site</a>',
            lambda result: 'href="https://evilsite.com"' in result and 'rel="noopener noreferrer"' in result and '>Evil Site</a>' in result
        ),
        (
            '<a href="https://evilsite.com">evilsite.com</a>',
            lambda result: 'href="https://evilsite.com"' in result and 'rel="noopener noreferrer"' in result
        ),
        (
            '<a href="https://evilsite.com">goodsite.com</a>',
            lambda result: 'href="https://evilsite.com"' in result and 'rel="noopener noreferrer"' in result and result.count('<a ') == 1
        ),
        (
            '<a href="https://goodsite.com.evilsite.com">goodsite.com</a>',
            lambda result: 'href="https://goodsite.com.evilsite.com"' in result and 'rel="noopener noreferrer"' in result
        ),
        (
            '<a href="https://evilsite.com/deep/path">evilsite.com</a>',
            lambda result: 'href="https://evilsite.com/deep/path"' in result and 'rel="noopener noreferrer"' in result
        ),
    ],
)
def test_linkify_abs(input_text, expected_check):
    result_snippet = rich_text_snippet(input_text, safelinks=False)
    result_full = rich_text(input_text, safelinks=False)
    result_email = markdown_compile_email(input_text)
    
    assert expected_check(result_snippet), f"rich_text_snippet failed for: {input_text}\nGot: {result_snippet}"
    assert expected_check(result_full), f"rich_text failed for: {input_text}\nGot: {result_full}"
    assert expected_check(result_email), f"markdown_compile_email failed for: {input_text}\nGot: {result_email}"


@pytest.mark.parametrize(
    "input_text,expected_behavior",
    [
        ("<script>alert(1)</script>", "xss_blocked"),
        ('<a href="javascript:alert(1)">Click</a>', "dangerous_protocol_removed"),
        ('<img src=x onerror="alert(1)">', "event_handler_removed"),
        ("Visit www.example.com today", "url_linkified"),
        ("Contact test@example.com", "email_linkified"),
        ('<a href="http://test.com">http://other.com</a>', "no_double_wrap"),
    ],
)
def test_nh3_security_and_linkification(input_text, expected_behavior):
    """
    Regression test for bleach→nh3 migration.
    Ensures XSS is blocked, linkification works, and no double-wrapping occurs.
    """
    if expected_behavior == "xss_blocked":
        result = clean_html(input_text)
        assert "<script" not in result.lower()
        assert "alert(" not in result

    elif expected_behavior == "dangerous_protocol_removed":
        result = clean_html(input_text)
        assert "javascript:" not in result.lower()
        assert 'rel="noopener noreferrer"' in result

    elif expected_behavior == "event_handler_removed":
        result = clean_html(input_text)
        assert "onerror" not in result.lower()
        assert "<img" not in result

    elif expected_behavior == "url_linkified":
        cleaned = clean_html(input_text)
        linkified = linkify_text(cleaned)
        assert '<a href=' in linkified
        assert "www.example.com" in linkified

    elif expected_behavior == "email_linkified":
        cleaned = clean_html(input_text)
        linkified = linkify_text(cleaned)
        assert 'href="mailto:test@example.com"' in linkified

    elif expected_behavior == "no_double_wrap":
        cleaned = clean_html(input_text)
        linkified = linkify_text(cleaned)
        assert linkified.count("<a ") == 1
        assert linkified.count("</a>") == 1
