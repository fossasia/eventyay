"""Tests for eventyay.common.sanitizers."""

import pytest

from eventyay.common.sanitizers import sanitize_email_html, sanitize_rich_text


class TestSanitizeRichText:
    def test_passthrough_safe_tags(self):
        html = '<p>Hello <strong>world</strong></p>'
        assert sanitize_rich_text(html) == html

    def test_passthrough_italic_underline(self):
        html = '<p><em>italic</em> and <u>underline</u></p>'
        assert sanitize_rich_text(html) == html

    def test_passthrough_lists(self):
        html = '<ul><li>one</li><li>two</li></ul>'
        assert sanitize_rich_text(html) == html

    def test_passthrough_ordered_list(self):
        html = '<ol><li>first</li><li>second</li></ol>'
        assert sanitize_rich_text(html) == html

    def test_passthrough_blockquote(self):
        html = '<blockquote><p>quoted</p></blockquote>'
        assert sanitize_rich_text(html) == html

    def test_passthrough_safe_link(self):
        result = sanitize_rich_text('<a href="https://example.com">link</a>')
        assert 'href="https://example.com"' in result
        assert 'link</a>' in result

    def test_http_link_allowed(self):
        result = sanitize_rich_text('<a href="http://example.com">link</a>')
        assert 'href="http://example.com"' in result

    def test_javascript_protocol_stripped(self):
        result = sanitize_rich_text('<a href="javascript:alert(1)">xss</a>')
        assert 'javascript:' not in result

    def test_data_uri_stripped(self):
        result = sanitize_rich_text('<a href="data:text/html,<script>alert(1)</script>">x</a>')
        assert 'data:' not in result

    def test_script_tag_stripped(self):
        result = sanitize_rich_text('<p>Hello</p><script>alert(1)</script>')
        assert '<script>' not in result
        assert 'alert(1)' not in result

    def test_onclick_attribute_stripped(self):
        result = sanitize_rich_text('<p onclick="evil()">text</p>')
        assert 'onclick' not in result

    def test_style_attribute_stripped(self):
        result = sanitize_rich_text('<p style="color:red">text</p>')
        assert 'style=' not in result

    def test_disallowed_tag_stripped(self):
        result = sanitize_rich_text('<div><p>keep</p></div>')
        assert '<div>' not in result
        assert '<p>keep</p>' in result

    def test_img_tag_stripped(self):
        result = sanitize_rich_text('<p>text</p><img src="x" onerror="alert(1)">')
        assert '<img' not in result

    def test_external_link_gets_rel(self):
        result = sanitize_rich_text('<a href="https://external.example.com">link</a>')
        assert 'noopener' in result
        assert 'noreferrer' in result

    def test_empty_string_returned_unchanged(self):
        assert sanitize_rich_text('') == ''

    def test_none_like_falsy_returned_unchanged(self):
        assert sanitize_rich_text('') == ''

    def test_plain_text_passthrough(self):
        result = sanitize_rich_text('<p>Just plain text.</p>')
        assert 'Just plain text.' in result

    def test_nested_xss_in_attribute(self):
        result = sanitize_rich_text('<p title="<script>alert(1)</script>">text</p>')
        assert '<script>' not in result

    def test_br_allowed(self):
        result = sanitize_rich_text('<p>line1<br>line2</p>')
        assert '<br>' in result or '<br/>' in result or '<br />' in result


class TestSanitizeEmailHtml:
    def test_passthrough_safe_tags(self):
        html = '<p>Hello <strong>world</strong></p>'
        assert sanitize_email_html(html) == html

    def test_span_allowed(self):
        result = sanitize_email_html('<p><span>chip</span> text</p>')
        assert '<span>chip</span>' in result

    def test_span_with_data_variable_preserved(self):
        result = sanitize_email_html('<span data-variable="name">{name}</span>')
        assert 'data-variable="name"' in result
        assert '{name}' in result

    def test_span_class_preserved(self):
        result = sanitize_email_html('<span class="tiptap-placeholder-chip">{name}</span>')
        assert 'class="tiptap-placeholder-chip"' in result

    def test_javascript_protocol_stripped(self):
        result = sanitize_email_html('<a href="javascript:alert(1)">xss</a>')
        assert 'javascript:' not in result

    def test_script_tag_stripped(self):
        result = sanitize_email_html('<p>text</p><script>evil()</script>')
        assert '<script>' not in result

    def test_external_link_no_rel_added(self):
        """Email profile must NOT inject rel attributes."""
        result = sanitize_email_html('<a href="https://example.com">link</a>')
        assert 'href="https://example.com"' in result
        assert 'noopener' not in result
        assert 'noreferrer' not in result

    def test_http_link_allowed(self):
        result = sanitize_email_html('<a href="http://example.com">link</a>')
        assert 'href="http://example.com"' in result

    def test_empty_string_returned_unchanged(self):
        assert sanitize_email_html('') == ''

    def test_onclick_stripped(self):
        result = sanitize_email_html('<a href="https://x.com" onclick="evil()">link</a>')
        assert 'onclick' not in result

    def test_img_stripped(self):
        result = sanitize_email_html('<img src="x" onerror="alert(1)">')
        assert '<img' not in result

    def test_disallowed_div_stripped(self):
        result = sanitize_email_html('<div><p>text</p></div>')
        assert '<div>' not in result
        assert '<p>text</p>' in result

    def test_rich_text_profile_subset(self):
        """Email profile allows all rich text tags plus span."""
        html = '<p><strong>bold</strong> <em>italic</em> <u>underline</u></p>'
        assert sanitize_email_html(html) == html
