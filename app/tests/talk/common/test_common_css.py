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
