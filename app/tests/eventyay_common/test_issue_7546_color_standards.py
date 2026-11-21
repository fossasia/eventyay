"""Tests for issue #7546: Replacing pure black with standard platform dark grey (#222222)."""

import re
from pathlib import Path

from django.contrib.staticfiles import finders


def test_agenda_css_comment_form_focus_border():
    """Verify _agenda.css comment form focus underline uses #222222 instead of pure black #000."""
    path = finders.find('agenda/css/_agenda.css')
    assert path, '_agenda.css not found'
    content = Path(path).read_text(encoding='utf-8')

    textarea_focus = re.search(r'\.youtube-comment-form textarea:focus\s*\{([^}]+)\}', content)
    assert textarea_focus, '.youtube-comment-form textarea:focus rule not found'
    rule_body = textarea_focus.group(1)
    assert 'border-bottom: 2px solid #222222;' in rule_body
    assert '#000' not in rule_body


def test_schedule_editor_vue_camera_icon():
    """Verify Talks schedule editor Session.vue uses #222222 for camera icon fill."""
    editor_session = Path(__file__).resolve().parents[2] / 'eventyay/webapp/schedule-editor/src/components/Session.vue'
    assert editor_session.exists(), 'schedule-editor Session.vue not found'
    content = editor_session.read_text(encoding='utf-8')

    # Match the .camera-body, .camera-lens Stylus selector block using indentation
    rule_match = re.search(
        r'([ \t]*)\.camera-body,\s*\.camera-lens\s*\n((?:\1[ \t]+[^\n]+\n?)+)',
        content,
    )
    assert rule_match, '.camera-body, .camera-lens block not found'
    rule_body = rule_match.group(2)
    assert 'fill: #222222' in rule_body
    assert '#000000' not in rule_body
    assert '#000' not in rule_body


def test_schedule_public_vue_camera_icon():
    """Verify Talks public schedule Session.vue uses #222222 for camera icon fill."""
    schedule_session = Path(__file__).resolve().parents[2] / 'eventyay/webapp/schedule/src/components/Session.vue'
    assert schedule_session.exists(), 'schedule Session.vue not found'
    content = schedule_session.read_text(encoding='utf-8')

    # Match the .do_not_record Pug block using indentation
    do_not_record_match = re.search(
        r'([ \t]*)\.do_not_record\(v-if="session\.do_not_record"[^)]*\)\s*\n((?:\1[ \t]+[^\n]+\n?)+)',
        content,
    )
    assert do_not_record_match, '.do_not_record block not found'
    svg_block = do_not_record_match.group(2)

    # Check rect element fill
    rect_match = re.search(r'rect\([^)]*style="([^"]+)"', svg_block)
    assert rect_match, 'rect element in .do_not_record SVG not found'
    assert 'fill:#222222;' in rect_match.group(1)
    assert 'fill:#000000;' not in rect_match.group(1)

    # Check camera path fill
    path_matches = re.findall(r'path\([^)]*style="([^"]+)"', svg_block)
    assert len(path_matches) >= 2, 'expected at least 2 path elements in .do_not_record SVG'
    camera_path_style = path_matches[0]
    assert 'fill:#222222;' in camera_path_style
    assert 'fill:#000000;' not in camera_path_style

    # Ensure no pure black remains anywhere in the SVG markup
    assert '#000000' not in svg_block
    assert '#000;' not in svg_block


def test_giftcards_css_design_token_compliance():
    """Verify Gift Cards stylesheet adheres to platform standards using CSS variables without raw black."""
    path = finders.find('pretixcontrol/css/giftcards.css')
    assert path, 'giftcards.css not found'
    content = Path(path).read_text(encoding='utf-8')

    # Confirm giftcards uses standard platform design tokens for text and backgrounds
    assert 'var(--color-text)' in content
    assert 'var(--color-text-muted)' in content
    assert 'var(--color-bg)' in content

    # Confirm giftcards does not use raw black colors
    assert '#000000' not in content
    assert '#000;' not in content
    assert re.search(r'(?<![-\w])color:\s*black\b', content) is None
