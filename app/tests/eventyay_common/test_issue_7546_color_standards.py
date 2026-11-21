"""Tests for issue #7546: Replacing pure black with standard platform dark grey (#222222)."""

import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders


# Pure black regex patterns covering all equivalent formats
PURE_BLACK_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Hex: #000, #000000, #000f, #000000ff (anchored by non-hex lookahead)
    re.compile(r'#(?:000000(?:ff)?|000(?:f)?)(?![0-9a-fA-F])', re.IGNORECASE),
    # Named color keyword 'black' (standalone token, not part of a hyphenated identifier or custom property)
    re.compile(r'(?<![-\w])black(?![-\w])', re.IGNORECASE),
    # rgb/rgba with 3 arguments (opaque black)
    re.compile(r'\brgba?\(\s*0%?\s*[, ]\s*0%?\s*[, ]\s*0%?\s*\)', re.IGNORECASE),
    # rgb/rgba with 4 arguments (alpha must be fully opaque: 1, 1.0, or 100%)
    re.compile(
        r'\brgba?\(\s*0%?\s*(?:,\s*|\s+)0%?\s*(?:,\s*|\s+)0%?\s*(?:,\s*|\/\s*)(?:1(?:\.0+)?|100%)\s*\)',
        re.IGNORECASE,
    ),
)

# Pattern matching quoted strings and real CSS comments outside of strings
CSS_COMMENT_TOKEN_PATTERN: re.Pattern[str] = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|(/\*.*?\*/)',
    re.DOTALL,
)

# Pattern matching quoted strings, URLs, and CSS comments in declaration values
DECLARATION_TOKEN_PATTERN: re.Pattern[str] = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|url\([^)]*\)|/\*.*?\*/',
    re.DOTALL,
)

# Canonical theme token requirements derived from actual Gift Cards CSS source
REQUIRED_GIFTCARDS_THEME_DECLARATIONS: dict[tuple[str, str], str] = {
    # var(--color-text) on core text containers and elements
    ('.gc-container', 'color'): 'var(--color-text)',
    ('.gc-title', 'color'): 'var(--color-text)',
    ('.gc-stat-value', 'color'): 'var(--color-text)',
    ('.gc-table td', 'color'): 'var(--color-text)',
    ('.gc-accepted-title', 'color'): 'var(--color-text)',
    # var(--color-text-muted) on secondary and muted elements
    ('.gc-breadcrumb', 'color'): 'var(--color-text-muted)',
    ('.gc-subtitle', 'color'): 'var(--color-text-muted)',
    ('.gc-stat-label', 'color'): 'var(--color-text-muted)',
    ('.gc-table th', 'color'): 'var(--color-text-muted)',
    ('.gc-empty-text', 'color'): 'var(--color-text-muted)',
    # var(--color-bg) on cards and layout containers
    ('.gc-header', 'background-color'): 'var(--color-bg)',
    ('.gc-card', 'background-color'): 'var(--color-bg)',
    ('.gc-stat-card', 'background-color'): 'var(--color-bg)',
    ('.gc-table-footer', 'background-color'): 'var(--color-bg)',
}


def strip_css_comments(css_text: str) -> str:
    """Strip CSS comments (/* ... */) while preserving comment-like text inside quoted strings."""

    def replacer(match: re.Match[str]) -> str:
        # If group 1 matched, it is a real CSS comment outside quotes -> replace with space
        if match.group(1):
            return ' '
        # Otherwise it is a quoted string literal -> preserve it intact
        return match.group(0)

    return CSS_COMMENT_TOKEN_PATTERN.sub(replacer, css_text)


def split_selector_list(selector_group: str) -> list[str]:
    """Split comma-separated selectors without breaking functional selectors like :is(), :not()."""
    selectors: list[str] = []
    current: list[str] = []
    paren_depth = 0

    for char in selector_group:
        if char == '(':
            paren_depth += 1
            current.append(char)
        elif char == ')':
            if paren_depth > 0:
                paren_depth -= 1
            current.append(char)
        elif char == ',' and paren_depth == 0:
            part = ''.join(current).strip()
            if part:
                selectors.append(part)
            current = []
        else:
            current.append(char)

    part = ''.join(current).strip()
    if part:
        selectors.append(part)

    return selectors


def extract_css_rules(css_text: str) -> dict[str, dict[str, str]]:
    """Parse a supported CSS subset into a mapping of selector -> {property: value} declarations.

    Supported CSS subset:
    - Standard rules and @media block nesting.
    - Selectors containing commas inside parentheses (e.g. :is(...), :not(...)).
    - Standard block-level comments (/* ... */), preserving strings containing comment syntax.
    - Semicolon-separated property: value declarations.
    """
    css_no_comments = strip_css_comments(css_text)
    rules: dict[str, dict[str, str]] = {}
    stack: list[str] = []
    current_text: list[str] = []

    for char in css_no_comments:
        if char == '{':
            header = ''.join(current_text).strip()
            current_text = []
            stack.append(header)
        elif char == '}':
            body = ''.join(current_text).strip()
            current_text = []
            header = stack.pop() if stack else ''
            if not header.startswith('@'):
                decls: dict[str, str] = {}
                for raw_item in body.split(';'):
                    item = raw_item.strip()
                    if ':' in item:
                        prop, val = item.split(':', 1)
                        decls[prop.strip().lower()] = val.strip()
                for sel in split_selector_list(header):
                    rules.setdefault(sel, {}).update(decls)
        else:
            current_text.append(char)

    return rules


def clean_css_declaration_value(val: str) -> str:
    """Strip CSS comments, quoted string contents, and URLs to prevent false positives."""

    def replacer(match: re.Match[str]) -> str:
        token = match.group(0)
        # Strip comments by replacing with whitespace to avoid accidental token merging
        if token.startswith('/*'):
            return ' '
        # Strip quoted strings and url(...) contents
        return ''

    return DECLARATION_TOKEN_PATTERN.sub(replacer, val)


def find_pure_black_in_declaration(prop: str, val: str) -> str | None:
    """Inspect a CSS declaration for pure-black color formats while avoiding false positives."""
    if prop.lower() in ('font', 'font-family'):
        return None
    clean_val = clean_css_declaration_value(val)
    for pattern in PURE_BLACK_PATTERNS:
        match = pattern.search(clean_val)
        if match:
            return match.group(0)
    return None


def parse_stylus_declarations(body: str) -> dict[str, str]:
    """Parse indentation-based Stylus rule body into a dictionary of declarations."""
    declarations: dict[str, str] = {}
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('//'):
            continue
        if ':' in line:
            prop, val = line.split(':', 1)
            declarations[prop.strip()] = val.strip().rstrip(';')
    return declarations


def parse_inline_style(style_str: str) -> dict[str, str]:
    """Parse an inline HTML/SVG style attribute string into a dictionary of declarations."""
    declarations: dict[str, str] = {}
    for raw_item in style_str.split(';'):
        item = raw_item.strip()
        if ':' in item:
            prop, val = item.split(':', 1)
            declarations[prop.strip()] = val.strip()
    return declarations


def validate_camera_fill_declaration(rule_body: str) -> tuple[bool, str | None]:
    """Validate that camera Stylus rule body contains exact #222222 fill without invalid suffixes or colors."""
    declarations = parse_stylus_declarations(rule_body)
    fill_val = declarations.get('fill')
    if fill_val is None:
        return False, "property 'fill' not found in declarations"
    if fill_val != '#222222':
        return False, f"expected exact fill '#222222', got '{fill_val}'"
    if re.search(r'^\s*fill:\s*#222222\s*$', rule_body, re.MULTILINE) is None:
        return False, 'multiline anchored fill pattern failed to match'
    if re.search(r'fill:\s*#222222[^\s;]+', rule_body) is not None:
        return False, 'fill declaration contains invalid trailing suffix characters'
    if find_pure_black_in_declaration('fill', fill_val) is not None:
        return False, 'fill declaration contains pure black'
    return True, None


def verify_giftcards_theme_tokens(rules: dict[str, dict[str, str]]) -> None:
    """Verify that expected theme tokens are present on the exact selectors and properties."""
    for (sel, prop), expected_val in REQUIRED_GIFTCARDS_THEME_DECLARATIONS.items():
        assert sel in rules, f"Expected selector '{sel}' not found in stylesheet rules"
        assert prop in rules[sel], f"Expected property '{prop}' not found on '{sel}'"
        assert rules[sel][prop] == expected_val, (
            f"Selector '{sel}' property '{prop}' has '{rules[sel][prop]}', expected '{expected_val}'"
        )


def test_agenda_css_comment_form_focus_border() -> None:
    """Verify _agenda.css comment form focus underline uses #222222 instead of pure black #000."""
    path = finders.find('agenda/css/_agenda.css')
    assert path, '_agenda.css not found'
    content = Path(path).read_text(encoding='utf-8')

    textarea_focus = re.search(r'\.youtube-comment-form textarea:focus\s*\{([^}]+)\}', content)
    assert textarea_focus, '.youtube-comment-form textarea:focus rule not found'
    rule_body = textarea_focus.group(1)

    decls: dict[str, str] = {}
    for raw_item in rule_body.split(';'):
        item = raw_item.strip()
        if ':' in item:
            prop, val = item.split(':', 1)
            decls[prop.strip().lower()] = val.strip()

    assert decls.get('border-bottom') == '2px solid #222222'
    for prop, val in decls.items():
        assert find_pure_black_in_declaration(prop, val) is None


def test_schedule_editor_vue_camera_icon() -> None:
    """Verify Talks schedule editor Session.vue uses exact #222222 fill for camera icon."""
    editor_session = Path(__file__).resolve().parents[2] / 'eventyay/webapp/schedule-editor/src/components/Session.vue'
    assert editor_session.exists(), 'schedule-editor Session.vue not found'
    content = editor_session.read_text(encoding='utf-8')

    rule_match = re.search(
        r'([ \t]*)(?P<selectors>\.camera-body\s*,\s*\.camera-lens)\s*\n(?P<body>(?:\1[ \t]+[^\n]+\n?)+)',
        content,
    )
    assert rule_match, '.camera-body, .camera-lens block not found'
    selector_line = rule_match.group('selectors')
    rule_body = rule_match.group('body')

    # Verify both .camera-body and .camera-lens are governed by the rule
    selectors = split_selector_list(selector_line)
    assert '.camera-body' in selectors, "'.camera-body' missing from selector group"
    assert '.camera-lens' in selectors, "'.camera-lens' missing from selector group"

    # Exact declaration matching through unified validation logic
    is_valid, error_msg = validate_camera_fill_declaration(rule_body)
    assert is_valid, error_msg

    declarations = parse_stylus_declarations(rule_body)
    assert declarations.get('stroke') == 'none'


def test_schedule_public_vue_camera_icon() -> None:
    """Verify Talks public schedule Session.vue uses #222222 for camera icon fill."""
    schedule_session = Path(__file__).resolve().parents[2] / 'eventyay/webapp/schedule/src/components/Session.vue'
    assert schedule_session.exists(), 'schedule Session.vue not found'
    content = schedule_session.read_text(encoding='utf-8')

    do_not_record_match = re.search(
        r'([ \t]*)\.do_not_record\(v-if="session\.do_not_record"[^)]*\)\s*\n((?:\1[ \t]+[^\n]+\n?)+)',
        content,
    )
    assert do_not_record_match, '.do_not_record block not found'
    svg_block = do_not_record_match.group(2)

    # Check rect element fill (camera body)
    rect_match = re.search(r'rect\([^)]*style="([^"]+)"', svg_block)
    assert rect_match, 'rect element in .do_not_record SVG not found'
    rect_decls = parse_inline_style(rect_match.group(1))
    assert rect_decls.get('fill') == '#222222', f"Camera body fill is '{rect_decls.get('fill')}', expected '#222222'"

    # Check camera path fill (camera lens)
    path_matches = re.findall(r'path\([^)]*style="([^"]+)"', svg_block)
    assert len(path_matches) >= 2, 'expected at least 2 path elements in .do_not_record SVG'
    camera_path_decls = parse_inline_style(path_matches[0])
    assert camera_path_decls.get('fill') == '#222222', (
        f"Camera lens fill is '{camera_path_decls.get('fill')}', expected '#222222'"
    )

    # Extract every inline style attribute separately and inspect each property/value pair
    style_attributes = re.findall(r'style="([^"]+)"', svg_block)
    assert style_attributes, 'No inline style attributes found in SVG markup'
    for style_attr in style_attributes:
        decls = parse_inline_style(style_attr)
        for prop, val in decls.items():
            hit = find_pure_black_in_declaration(prop, val)
            assert hit is None, f"Pure black detected in SVG style declaration '{prop}: {val}' ({hit})"

    assert '#000000' not in svg_block
    assert '#000;' not in svg_block


def test_svg_inline_style_pure_black_detection() -> None:
    """Demonstrate that pure-black formats in inline SVG styles fail and valid #222222 passes."""
    # Valid #222222 style passes
    valid_style = 'fill:#222222;stroke:none;'
    valid_decls = parse_inline_style(valid_style)
    assert valid_decls.get('fill') == '#222222'
    for prop, val in valid_decls.items():
        assert find_pure_black_in_declaration(prop, val) is None

    # style="fill: black" is detected as pure black
    black_named = parse_inline_style('fill: black; stroke: none')
    assert find_pure_black_in_declaration('fill', black_named['fill']) is not None

    # style="fill: rgb(0, 0, 0)" is detected as pure black
    black_rgb = parse_inline_style('fill: rgb(0, 0, 0); stroke: none')
    assert find_pure_black_in_declaration('fill', black_rgb['fill']) is not None


def test_giftcards_css_design_token_compliance() -> None:
    """Verify Gift Cards stylesheet uses expected theme tokens on specific selectors without raw black."""
    path = finders.find('pretixcontrol/css/giftcards.css')
    assert path, 'giftcards.css not found'
    content = Path(path).read_text(encoding='utf-8')

    rules = extract_css_rules(content)

    # Finding 1: Verify exact theme tokens on the correct selectors and declarations
    verify_giftcards_theme_tokens(rules)

    # Finding 2: Detect any pure-black color declarations in any format across all rules
    black_violations: list[tuple[str, str, str, str]] = []
    for sel, decls in rules.items():
        for prop, val in decls.items():
            hit = find_pure_black_in_declaration(prop, val)
            if hit:
                black_violations.append((sel, prop, val, hit))

    assert not black_violations, f'Pure black declarations detected in giftcards.css: {black_violations}'


def test_giftcards_rejects_fixed_black_color_formats() -> None:
    """Demonstrate that all equivalent pure-black formats are detected and rejected."""
    black_variants = [
        '#000',
        '#000000',
        '#000 !important',
        '#000000 !important',
        'black',
        'black !important',
        'rgb(0, 0, 0)',
        'rgb(0,0,0)',
        'rgba(0, 0, 0, 1)',
        'rgba(0,0,0,1)',
        'rgba(0, 0, 0, 1.0)',
        'rgba(0, 0, 0, 100%)',
        'rgb(0 0 0 / 1)',
        'rgb(0 0 0 / 100%)',
        'rgba(0 0 0 / 1)',
        '#000f',
        '#000000ff',
    ]

    for variant in black_variants:
        detected = find_pure_black_in_declaration('color', variant)
        assert detected is not None, f"Expected pure-black variant '{variant}' to be detected"

    # Verify standalone 'black' keyword vs legitimate custom property references
    assert find_pure_black_in_declaration('color', 'black') is not None
    assert find_pure_black_in_declaration('border', '1px solid black') is not None
    assert find_pure_black_in_declaration('color', 'var(--black)') is None
    assert find_pure_black_in_declaration('color', 'var(--color-black)') is None

    # Verify font-family does not trigger false positives for Black weight
    assert find_pure_black_in_declaration('font-family', 'Roboto Black, sans-serif') is None


def test_pure_black_detection_ignores_transparent_and_semitransparent() -> None:
    """Demonstrate that transparent and valid semi-transparent black values are not flagged."""
    safe_values = [
        'transparent',
        'rgba(0, 0, 0, 0)',
        'rgba(0, 0, 0, 0.0)',
        'rgba(0, 0, 0, 0.5)',
        'rgba(0, 0, 0, 0.85)',
        'rgb(0 0 0 / 0.5)',
        'rgb(0 0 0 / 0)',
        '#0000',  # 4-digit hex with alpha 0
        '#00000000',  # 8-digit hex with alpha 0
        '#00000080',  # 8-digit hex with 50% alpha
        '#0001',  # 4-digit hex with partial alpha
        '#000001',  # dark blue-grey, not pure black
        '#222222',
        'var(--black)',
        'var(--color-black)',
        'var(--color-text)',
        'var(--color-text-muted)',
        'var(--color-bg)',
    ]
    for safe_val in safe_values:
        assert find_pure_black_in_declaration('color', safe_val) is None, (
            f"Expected '{safe_val}' not to be flagged as pure black"
        )


def test_pure_black_detection_comment_and_string_isolation() -> None:
    """Demonstrate that comments are stripped while quoted strings and URLs avoid false positives."""
    # Comment containing black color name should be stripped and not flagged
    assert find_pure_black_in_declaration('color', '/* black */ #222222') is None

    # Comment alongside actual black hex should properly detect the black hex
    assert find_pure_black_in_declaration('color', '/* note */ #000') is not None

    # Quoted string containing black should not trigger false positive
    assert find_pure_black_in_declaration('content', '"/* not a comment */ black"') is None
    assert find_pure_black_in_declaration('content', "'black'") is None

    # URL containing black should not trigger false positive
    assert find_pure_black_in_declaration('background', 'url("https://example.com/black.png")') is None


def test_css_comment_handling_preserves_quoted_strings() -> None:
    """Verify that CSS comments inside quoted strings are preserved while real comments are stripped."""
    sample_css = """
    /* outer header comment */
    .icon-quote::before {
        content: "/* not a comment */";
        color: var(--color-text); /* inline comment */
    }
    .icon-single::after {
        content: '/* also not a comment */';
    }
    """
    rules = extract_css_rules(sample_css)
    assert '.icon-quote::before' in rules
    assert rules['.icon-quote::before']['content'] == '"/* not a comment */"'
    assert rules['.icon-quote::before']['color'] == 'var(--color-text)'
    assert '.icon-single::after' in rules
    assert rules['.icon-single::after']['content'] == "'/* also not a comment */'"


def test_extract_css_rules_functional_selectors() -> None:
    """Verify that selectors with commas inside parentheses (:is, :not) are not incorrectly split."""
    sample_css = """
    .btn:is(.primary, .accent), .card:not(.disabled, .muted) {
        color: var(--color-text);
    }
    """
    rules = extract_css_rules(sample_css)
    assert '.btn:is(.primary, .accent)' in rules
    assert '.card:not(.disabled, .muted)' in rules
    assert len(rules) == 2
    assert rules['.btn:is(.primary, .accent)']['color'] == 'var(--color-text)'


def test_giftcards_theme_token_mismatch_fails() -> None:
    """Demonstrate that using a wrong theme token or hardcoded color on a selector fails."""
    # Test wrong token: using var(--color-bg) where var(--color-text) is required
    mock_rules_wrong_token = {
        '.gc-container': {'color': 'var(--color-bg)'},
    }
    with pytest.raises(AssertionError, match='has.*expected'):
        verify_giftcards_theme_tokens(mock_rules_wrong_token)

    # Test hardcoded color instead of token
    mock_rules_hardcoded = {
        '.gc-container': {'color': '#111111'},
    }
    with pytest.raises(AssertionError, match='has.*expected'):
        verify_giftcards_theme_tokens(mock_rules_hardcoded)

    # Test missing required selector
    mock_rules_missing = {
        '.gc-other': {'color': 'var(--color-text)'},
    }
    with pytest.raises(AssertionError, match='not found in stylesheet rules'):
        verify_giftcards_theme_tokens(mock_rules_missing)


def test_camera_declaration_matching_exactness() -> None:
    """Demonstrate that invalid suffixes (e.g. #222222x, #22222200) fail and exact #222222 passes."""
    # Valid declaration passes through the exact same validation logic
    valid_body = 'fill: #222222\nstroke: none'
    is_valid, error_msg = validate_camera_fill_declaration(valid_body)
    assert is_valid, error_msg

    # Invalid suffix fails exact declaration check
    invalid_suffix = 'fill: #222222x\nstroke: none'
    is_valid, msg = validate_camera_fill_declaration(invalid_suffix)
    assert not is_valid
    assert msg and '#222222x' in msg

    # Extra digits fail
    invalid_extra = 'fill: #22222200\nstroke: none'
    is_valid, msg = validate_camera_fill_declaration(invalid_extra)
    assert not is_valid
    assert msg and '#22222200' in msg

    # Pure black formats fail
    for black_fill in ('fill: #000000', 'fill: #000', 'fill: black', 'fill: rgb(0, 0, 0)'):
        is_valid, _ = validate_camera_fill_declaration(f'{black_fill}\nstroke: none')
        assert not is_valid
