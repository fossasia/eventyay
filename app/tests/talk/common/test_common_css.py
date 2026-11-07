from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from reportlab.pdfbase.ttfonts import TTFontFile

from eventyay.common.text.css import validate_css


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
    font_files = [
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

    for fname in font_files:
        font_path = fonts_dir / fname
        assert font_path.is_file(), f'Font file {font_path} does not exist'
        ttfont = TTFontFile(str(font_path))
        assert ttfont.numGlyphs > 500, f'{fname} has only {ttfont.numGlyphs} glyphs'
        for cp in required_codepoints:
            assert cp in ttfont.charToGlyph, f'Character U+{cp:04X} ({chr(cp)}) missing in {fname}'


def test_open_sans_css_declarations():
    static_dir = Path(__file__).resolve().parents[3] / 'eventyay' / 'static'
    open_sans_css = (static_dir / 'common' / 'css' / 'open_sans.css').read_text(encoding='utf-8')
    fonts_css = (static_dir / 'common' / 'css' / '_fonts.css').read_text(encoding='utf-8')

    for content, filename in [(open_sans_css, 'open_sans.css'), (fonts_css, '_fonts.css')]:
        assert 'opensans_regular_macroman' not in content, f'{filename} still references macroman subset'
        assert 'opensans_bold_macroman' not in content, f'{filename} still references macroman subset'
        assert '../../fonts/OpenSans-Regular.ttf' in content
        assert '../../fonts/OpenSans-Bold.ttf' in content
        assert '../../fonts/OpenSans-Italic.ttf' in content
        assert '../../fonts/OpenSans-BoldItalic.ttf' in content
        assert 'font-display: swap' in content


def test_open_sans_stylesheet_included_in_templates():
    eventyay_dir = Path(__file__).resolve().parents[3] / 'eventyay'
    templates = [
        eventyay_dir / 'presale' / 'templates' / 'pretixpresale' / 'base.html',
        eventyay_dir / 'control' / 'templates' / 'pretixcontrol' / 'base.html',
        eventyay_dir / 'eventyay_common' / 'templates' / 'eventyay_common' / 'base.html',
    ]

    for tpl in templates:
        assert tpl.is_file(), f'Template {tpl} does not exist'
        content = tpl.read_text(encoding='utf-8')
        assert 'common/css/open_sans.css' in content, f'open_sans.css not included in {tpl.name}'
