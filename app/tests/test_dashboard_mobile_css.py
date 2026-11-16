import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "eventyay" / "static"
NAV_CSS = STATIC / "common" / "css" / "_component_nav_mobile.css"
DASHBOARD_CSS = STATIC / "eventyay-common" / "css" / "common_dashboard.css"


def media_blocks(css, max_width):
    """Return the bodies of all @media (max-width: <max_width>px) blocks."""
    pattern = rf"@media\s*\(\s*max-width\s*:\s*{max_width}px\s*\)\s*\{{"
    blocks = []
    for match in re.finditer(pattern, css):
        depth, i = 1, match.end()
        while depth and i < len(css):
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        blocks.append(css[match.end() : i - 1])
    return blocks


def test_nav_buttons_wrap_on_small_screens():
    blocks = media_blocks(NAV_CSS.read_text(encoding="utf-8"), 480)
    assert blocks, "missing 480px block for the component nav"
    block = blocks[0]
    assert re.search(r"flex-wrap:\s*wrap", block)
    assert re.search(r"overflow-wrap:\s*anywhere", block)


def test_timeline_steps_and_popups_fit_on_mobile():
    blocks = media_blocks(DASHBOARD_CSS.read_text(encoding="utf-8"), 767)
    block = next((b for b in blocks if ".timeline-step" in b), "")
    assert block, "missing 767px timeline block"
    assert re.search(r"\.timeline-step\s*\{[^}]*min-width:\s*0", block)
    assert "inset-inline-start" in block
    assert "inset-inline-end" in block
    assert re.search(r"overflow-wrap:\s*anywhere", block)