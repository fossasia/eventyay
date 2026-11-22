"""Tests for issue #7546: Replacing pure black colors with standard platform dark grey (#222222)."""

import re
from pathlib import Path

from django.contrib.staticfiles import finders


def test_agenda_css_comment_form_focus_border():
    """Verify _agenda.css comment form focus border uses #222222 instead of pure black #000."""
    path = finders.find('agenda/css/_agenda.css')
    assert path, '_agenda.css not found'
    content = Path(path).read_text(encoding='utf-8')

    match = re.search(r'\.youtube-comment-form textarea:focus\s*\{([^}]+)\}', content)
    assert match, '.youtube-comment-form textarea:focus rule not found'
    body = match.group(1)
    assert 'border-bottom: 2px solid #222222;' in body
    assert '#000' not in body


def test_schedule_editor_vue_camera_icon():
    """Verify Talks schedule editor Session.vue uses #222222 for camera icon fill."""
    session_file = Path(__file__).resolve().parents[2] / 'eventyay/webapp/schedule-editor/src/components/Session.vue'
    assert session_file.exists(), 'schedule-editor Session.vue not found'
    content = session_file.read_text(encoding='utf-8')

    match = re.search(r'\.camera-body,\s*\.camera-lens\s*\n\s*fill:\s*([^\n]+)', content)
    assert match, '.camera-body, .camera-lens fill rule not found'
    assert match.group(1).strip() == '#222222'


def test_schedule_public_vue_camera_icon():
    """Verify Talks public schedule Session.vue uses #222222 for camera icon fill."""
    session_file = Path(__file__).resolve().parents[2] / 'eventyay/webapp/schedule/src/components/Session.vue'
    assert session_file.exists(), 'schedule Session.vue not found'
    content = session_file.read_text(encoding='utf-8')

    do_not_record_match = re.search(
        r'\.do_not_record\(v-if="session\.do_not_record"[^)]*\)\s*\n((?:[ \t]+[^\n]+\n?)+)',
        content,
    )
    assert do_not_record_match, '.do_not_record block not found'
    svg_block = do_not_record_match.group(1)

    assert 'fill:#222222;' in svg_block
    assert 'fill:#000000;' not in svg_block
    assert '#000' not in svg_block


def test_quicksetup_css_color_standards():
    """Verify quicksetup.css uses #222222 instead of #000000 for button hover and active stepper labels."""
    path = finders.find('pretixcontrol/css/quicksetup.css')
    assert path, 'quicksetup.css not found'
    content = Path(path).read_text(encoding='utf-8')

    skip_hover = re.search(r'\.btn-skip:hover\s*\{([^}]+)\}', content)
    assert skip_hover, '.btn-skip:hover rule not found'
    assert 'color: #222222;' in skip_hover.group(1)
    assert '#000000' not in skip_hover.group(1)

    step_active = re.search(r'\.quickstart-step-item\.active \.step-label[^{]*\{([^}]+)\}', content)
    assert step_active, '.quickstart-step-item.active .step-label rule not found'
    assert 'color: #222222;' in step_active.group(1)
    assert '#000000' not in step_active.group(1)


def test_order_overview_css_tooltip_color_standards():
    """Verify order-overview.css custom tooltips use #222222 instead of #000 for text and border colors."""
    path = finders.find('pretixcontrol/css/order-overview.css')
    assert path, 'order-overview.css not found'
    content = Path(path).read_text(encoding='utf-8')

    tooltip_inner = re.search(r'\.order-overview \.tooltip-inner\s*\{([^}]+)\}', content)
    assert tooltip_inner, '.order-overview .tooltip-inner rule not found'
    body = tooltip_inner.group(1)
    assert 'color: #222222;' in body
    assert 'border: 1px solid #222222;' in body
    assert '#000' not in body

    for arrow_dir in ('top', 'bottom', 'right', 'left'):
        arrow_match = re.search(rf'\.order-overview \.tooltip\.{arrow_dir} \.tooltip-arrow\s*\{{([^}}]+)\}}', content)
        assert arrow_match, f'tooltip {arrow_dir} arrow rule not found'
        assert f'border-{arrow_dir}-color: #222222;' in arrow_match.group(1)


def test_giftcards_css_design_token_compliance():
    """Verify giftcards.css uses standard platform tokens and does not introduce hardcoded pure black."""
    path = finders.find('pretixcontrol/css/giftcards.css')
    assert path, 'giftcards.css not found'
    content = Path(path).read_text(encoding='utf-8')

    assert 'var(--color-text)' in content
    assert 'var(--color-text-muted)' in content
    assert 'var(--color-bg)' in content
    assert '#000000' not in content
    assert re.search(r':\s*#000\b', content) is None
