import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.template.loader import get_template
from fontTools.ttLib import TTFont
from reportlab.pdfbase.ttfonts import TTFontFile

from eventyay.common.text.css import validate_css
from eventyay.presale.style import compile_scss


@pytest.fixture
def valid_css():
    return """
body {
  background-color: #000;
  display: none;
}
.some-descriptor {
  /* Dotted borders are IN! */
  border-style: dotted dashed solid double;  /* more commenting */
  BORDER-color: red green blue yellow;
  object-fit: cover;
}
#best-descriptor {
  border: 5px solid red;
}
@media print {
  #best-descriptor {
    border: 5px solid blue;
  }
}
"""


@pytest.fixture
def invalid_css(valid_css):
    return (
        valid_css
        + """
a.other-descriptor {
    content: url("https://malicious.site.com");
}
"""
    )


def test_valid_css(valid_css):
    assert validate_css(valid_css) == valid_css


def test_invalid_css(invalid_css):
    with pytest.raises(ValidationError):
        validate_css(invalid_css)


def test_contact_organizer_button_css_rules():
    css_path = finders.find('common/css/_contact_modal.css')
    assert css_path is not None
    css_content = Path(css_path).read_text(encoding='utf-8')

    # Base styling uses event-themed link color
    assert '.contact-organizer-btn' in css_content
    assert 'footer .contact-organizer-btn' in css_content
    assert 'color: var(--color-primary-text, var(--color-primary, inherit));' in css_content
    assert 'display: inline;' in css_content

    # Hover styling
    hover_color = 'color: var(--color-primary-text-dark, var(--color-primary-hover, var(--color-primary, inherit)));'
    assert '.contact-organizer-btn:hover' in css_content
    assert 'footer .contact-organizer-btn:hover' in css_content
    assert hover_color in css_content
    assert 'text-decoration: underline;' in css_content

    # Focus styling preserves keyboard outline for accessibility
    assert '.contact-organizer-btn:focus' in css_content
    assert 'footer .contact-organizer-btn:focus' in css_content
    assert 'outline: 2px solid var(--color-primary, currentColor);' in css_content
    assert 'outline-offset: 2px;' in css_content

    # Non-visible focus suppresses outline only when :focus-visible is supported
    assert '.contact-organizer-btn:focus:not(:focus-visible)' in css_content
    assert 'footer .contact-organizer-btn:focus:not(:focus-visible)' in css_content

    # Active styling
    assert '.contact-organizer-btn:active' in css_content
    assert 'footer .contact-organizer-btn:active' in css_content
    assert 'color: var(--color-primary-text-dark, var(--color-primary, inherit));' in css_content


def test_open_sans_font_assets_exist_and_contain_eastern_european_glyphs():
    fonts_dir = Path(__file__).resolve().parents[3] / 'eventyay' / 'static' / 'fonts'
    woff2_files = [
        'OpenSans-Regular.woff2',
        'OpenSans-Bold.woff2',
        'OpenSans-Italic.woff2',
        'OpenSans-BoldItalic.woff2',
    ]
    ttf_files = [
        'OpenSans-Regular.ttf',
        'OpenSans-Bold.ttf',
        'OpenSans-Italic.ttf',
        'OpenSans-BoldItalic.ttf',
    ]
    # Central/Eastern European characters:
    # Ą, ą, Č, č, Ę, ę, Ł, ł, Ń, ń, Š, š, Ž, ž
    required_codepoints = [
        0x0104,
        0x0105,
        0x010C,
        0x010D,
        0x0118,
        0x0119,
        0x0141,
        0x0142,
        0x0143,
        0x0144,
        0x0160,
        0x0161,
        0x017D,
        0x017E,
    ]

    # Verify WOFF2 assets (used for web font delivery)
    for fname in woff2_files:
        font_path = fonts_dir / fname
        assert font_path.is_file(), f'WOFF2 font file {font_path} does not exist'
        font = TTFont(font_path)
        glyph_count = len(font.getGlyphOrder())
        assert glyph_count > 500, f'{fname} has only {glyph_count} glyphs'
        cmap = font.getBestCmap()
        for cp in required_codepoints:
            assert cp in cmap, f'Character U+{cp:04X} ({chr(cp)}) missing in {fname}'

    # Verify original TTF assets (preserved for ReportLab PDF generation)
    for fname in ttf_files:
        font_path = fonts_dir / fname
        assert font_path.is_file(), f'TTF font file {font_path} does not exist'
        ttfont = TTFontFile(str(font_path))
        assert ttfont.numGlyphs > 500, f'{fname} has only {ttfont.numGlyphs} glyphs'
        for cp in required_codepoints:
            assert cp in ttfont.charToGlyph, f'Character U+{cp:04X} ({chr(cp)}) missing in {fname}'


def test_open_sans_css_declarations():
    fonts_css_path = finders.find('common/css/_fonts.css')
    assert fonts_css_path is not None
    content = Path(fonts_css_path).read_text(encoding='utf-8')

    assert 'macroman' not in content
    assert '../../fonts/OpenSans-Regular.woff2' in content
    assert '../../fonts/OpenSans-Bold.woff2' in content
    assert '../../fonts/OpenSans-Italic.woff2' in content
    assert '../../fonts/OpenSans-BoldItalic.woff2' in content
    assert 'format("woff2")' in content
    assert 'font-display: swap' in content


def test_open_sans_stylesheet_included_in_templates():
    template_names = [
        'pretixpresale/base.html',
        'pretixcontrol/base.html',
        'eventyay_common/base.html',
    ]

    for template_name in template_names:
        template = get_template(template_name)
        assert 'common/css/_fonts.css' in template.template.source, f'_fonts.css not included in {template_name}'


def test_organizer_custom_primary_font_precedence_in_presale_template():
    class DummySettings:
        def __init__(self, data):
            self._data = data

        def get(self, key, default=None, **_kwargs):
            return self._data.get(key, default)

    organizer = SimpleNamespace(settings=DummySettings({'primary_font': 'Georgia'}))
    compiled_css, _ = compile_scss(organizer)
    assert ':root{--font-family:Georgia,' in compiled_css
    assert '--font-family-title:Georgia,' in compiled_css

    fonts_css_path = finders.find('common/css/_fonts.css')
    assert fonts_css_path is not None
    fonts_css = Path(fonts_css_path).read_text(encoding='utf-8')
    assert ':where(:root)' in fonts_css
    assert not fonts_css.lstrip().startswith(':root')
    assert '\n:root' not in fonts_css

    dummy_gso = SimpleNamespace(settings=DummySettings({}))
    context = {
        'css_file': '/media/pub/org/presale.1234.css',
        'site_name': 'Eventyay',
        'settings': SimpleNamespace(),
        'django_settings': SimpleNamespace(INSTANCE_NAME='Eventyay', DEBUG=True),
        'request': SimpleNamespace(
            event=None,
            organizer=SimpleNamespace(slug='org', name='Org'),
            user=SimpleNamespace(is_authenticated=False),
            resolver_match=None,
            LANGUAGE_CODE='en',
            path='/org/',
            build_absolute_uri=lambda: 'https://example.com/org/',
        ),
    }

    with (
        patch('eventyay.base.settings.GlobalSettingsObject', return_value=dummy_gso),
        patch('eventyay.base.templatetags.privacy_consent.GlobalSettingsObject', return_value=dummy_gso),
    ):
        presale_html = get_template('pretixpresale/base.html').render(context)
        base_public_html = get_template('common/base_public.html').render(context)

    assert presale_html.count('common/css/_fonts.css') == 1
    assert base_public_html.count('common/css/_fonts.css') == 1
    assert presale_html.index('/media/pub/org/presale.1234.css') < presale_html.index('common/css/_fonts.css')


def extract_media_blocks(css_content: str) -> list[tuple[str, str]]:
    """Extract all @media query blocks as (header, body) tuples using balanced braces."""
    blocks: list[tuple[str, str]] = []
    i = 0
    n = len(css_content)
    in_string: str | None = None
    in_comment = False
    mode = 'OUTSIDE'
    media_start = 0
    body_start = 0
    depth = 0
    header = ''

    while i < n:
        c = css_content[i]
        if in_comment:
            if c == '*' and i + 1 < n and css_content[i + 1] == '/':
                in_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string is not None:
            if c == '\\':
                i += 2
            elif c == in_string:
                in_string = None
                i += 1
            else:
                i += 1
            continue

        if c == '/' and i + 1 < n and css_content[i + 1] == '*':
            in_comment = True
            i += 2
            continue
        if c in ('"', "'"):
            in_string = c
            i += 1
            continue

        if mode == 'OUTSIDE':
            if (
                css_content.startswith('@media', i)
                and (i == 0 or not (css_content[i - 1].isalnum() or css_content[i - 1] in '_-'))
                and (i + 6 < n and (css_content[i + 6].isspace() or css_content[i + 6] in ('(', '{')))
            ):
                media_start = i
                mode = 'HEADER'
                i += 6
                continue
        elif mode == 'HEADER':
            if c == '{':
                header = css_content[media_start:i].strip()
                body_start = i + 1
                depth = 1
                mode = 'BODY'
        elif mode == 'BODY':
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    blocks.append((header, css_content[body_start:i]))
                    mode = 'OUTSIDE'

        i += 1

    return blocks


def extract_kpi_mobile_media_block(css_content: str) -> tuple[str, str]:
    """Extract the single @media block containing .od-kpi-grid and verify it is at max-width: 767px."""
    media_blocks = extract_media_blocks(css_content)
    kpi_media_blocks = [(header, body) for header, body in media_blocks if '.od-kpi-grid' in body]
    assert len(kpi_media_blocks) == 1, (
        f'Expected exactly 1 media block containing .od-kpi-grid, found {len(kpi_media_blocks)}'
    )
    header, body = kpi_media_blocks[0]
    assert re.search(r'max-width:\s*767px', header) is not None, f'Expected max-width: 767px media query, got: {header}'
    return header, body


def test_organizer_dashboard_kpi_responsive_layout():
    css_path = finders.find('eventyay-common/css/common_dashboard.css')
    assert css_path is not None
    css_content = Path(css_path).read_text(encoding='utf-8')

    # .od-kpi-grid uses responsive auto-fit / minmax sizing rule with a six-column cap
    kpi_grid_match = re.search(r'\.od-kpi-grid\s*\{([^}]+)\}', css_content)
    assert kpi_grid_match is not None
    kpi_grid_rules = kpi_grid_match.group(1)
    assert 'repeat(auto-fit, minmax(max(170px, calc((100% - 5 * 12px) / 6)), 1fr))' in kpi_grid_rules

    # .od-kpi-label includes overflow-wrap: anywhere
    kpi_label_match = re.search(r'\.od-kpi-label\s*\{([^}]+)\}', css_content)
    assert kpi_label_match is not None
    kpi_label_rules = kpi_label_match.group(1)
    assert 'overflow-wrap: anywhere' in kpi_label_rules

    # Obsolete 1200px and 991px fixed-column overrides are absent
    media_blocks = extract_media_blocks(css_content)
    for header, body in media_blocks:
        if '1200px' in header or '991px' in header:
            assert '.od-kpi-grid' not in body

    # Existing mobile breakpoint (767px) is preserved and contains .od-kpi-grid with 1fr
    header, body = extract_kpi_mobile_media_block(css_content)
    rule_match = re.search(r'([^{}]*\.od-kpi-grid[^{]*)\{([^}]+)\}', body)
    assert rule_match is not None
    assert re.search(r'(?:^|;)\s*grid-template-columns:\s*1fr\s*(?:;|$)', rule_match.group(2)) is not None

    # .od-kpi-grid is defined in base layout and the mobile media query only
    assert len(re.findall(r'\.od-kpi-grid\b', css_content)) == 2


def test_organizer_dashboard_kpi_rejects_600px_mobile_breakpoint():
    css_path = finders.find('eventyay-common/css/common_dashboard.css')
    assert css_path is not None
    css_content = Path(css_path).read_text(encoding='utf-8')

    modified_css = css_content.replace(
        '@media (max-width:767px) {\n  .od-header',
        '@media (max-width:600px) {\n  .od-header',
    )
    assert modified_css != css_content

    # Moving the organizer grid rule to a 600px breakpoint must be rejected
    with pytest.raises(AssertionError, match=r'Expected max-width: 767px media query, got: @media \(max-width:600px\)'):
        extract_kpi_mobile_media_block(modified_css)


def test_organizer_dashboard_kpi_rejects_multi_column_mobile_declaration():
    css_path = finders.find('eventyay-common/css/common_dashboard.css')
    assert css_path is not None
    css_content = Path(css_path).read_text(encoding='utf-8')

    modified_css = css_content.replace(
        '.od-kpi-grid {\n    grid-template-columns: 1fr',
        '.od-kpi-grid {\n    grid-template-columns: 1fr 1fr',
    )
    assert modified_css != css_content

    header, body = extract_kpi_mobile_media_block(modified_css)
    rule_match = re.search(r'([^{}]*\.od-kpi-grid[^{]*)\{([^}]+)\}', body)
    assert rule_match is not None
    with pytest.raises(AssertionError):
        assert re.search(r'(?:^|;)\s*grid-template-columns:\s*1fr\s*(?:;|$)', rule_match.group(2)) is not None
