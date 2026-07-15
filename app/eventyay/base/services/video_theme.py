"""Video SPA theme derived from Common Settings plus stored event.config['theme']."""

import re

from eventyay.multidomain.urlreverse import eventreverse, mainreverse
from eventyay.presale.style import SYSTEM_FONTS, get_fonts, get_font_stylesheet, resolve_font

_VALID_HEX_6 = re.compile(r'^#[0-9a-f]{6}$')

# Match tickets/talk sidebars (pretixcontrol/orga); not driven by primary colour.
PLATFORM_SIDEBAR_BG = '#f8f8f8'


def normalize_video_theme_hex(value, fallback='#2185d0'):
    """Normalize to lowercase #rrggbb for the video SPA (theme.js); invalid values use fallback."""
    fb = fallback.lower() if isinstance(fallback, str) else '#2185d0'
    if not _VALID_HEX_6.match(fb):
        fb = '#2185d0'

    if value is None:
        return fb
    v = str(value).strip().lower()
    if not v:
        return fb
    if not v.startswith('#'):
        v = f'#{v.lstrip("#")}'

    candidate = None
    if len(v) == 4 and v.startswith('#'):
        candidate = f'#{v[1]}{v[1]}{v[2]}{v[2]}{v[3]}{v[3]}'
    elif len(v) == 7:
        candidate = v

    if candidate and _VALID_HEX_6.match(candidate):
        return candidate
    return fb


def build_video_typography_for_event(event):
    """Typography tokens shared with presale/agenda (Common Settings primary_font)."""
    resolved_font, font_family_value = resolve_font(event)
    typography = {
        'settings_css_url': str(event.urls.settings_css),
    }
    if font_family_value:
        typography['font_family'] = font_family_value
        typography['font_family_title'] = font_family_value
    if resolved_font and resolved_font not in SYSTEM_FONTS:
        fonts_dict = get_fonts()
        if resolved_font in fonts_dict:
            typography['font_stylesheet'] = get_font_stylesheet(
                resolved_font,
                fonts=fonts_dict,
                for_sass=False,
            )
    return typography


def build_video_theme_for_event(event):
    """
    Theme payload for the video SPA injection and world.config.get.

    Navbar colours follow Common Settings (primary, header colours, page
    background). The rooms sidebar uses the platform default light style.
    Remaining keys are taken from event.config['theme'] (identicons, text
    overwrites, stream offline image, custom css flag, etc.).
    """
    cfg = event.config or {}
    stored = cfg.get('theme')
    if not isinstance(stored, dict):
        stored = {}
    out = {**stored}

    primary = normalize_video_theme_hex(event.visible_primary_color, '#2185d0')
    page_bg = event.settings.get('theme_color_background') or '#f5f5f5'
    bbb_bg = normalize_video_theme_hex(page_bg, '#ffffff')
    header_background = event.settings.get('header_background_color')
    header_text = event.settings.get('header_text_color')

    existing_colors = out.get('colors')
    if not isinstance(existing_colors, dict):
        existing_colors = {}
    else:
        existing_colors = {**existing_colors}

    colors = {
        **existing_colors,
        'primary': primary,
        'sidebar': event.settings.get('video_sidebar_background_color') or PLATFORM_SIDEBAR_BG,
        'sidebar_text': event.settings.get('video_sidebar_text_color') or '#000000',
        'sidebar_hover': event.settings.get('video_sidebar_hover_color') or '#2185d0',
        'bbb_background': bbb_bg,
    }
    if header_background:
        colors['header_background'] = normalize_video_theme_hex(header_background, primary)
    if header_text:
        colors['header_text'] = normalize_video_theme_hex(header_text, '#ffffff')
    out['colors'] = colors

    navigation = {
        'presale_home_url': str(event.urls.base),
        'site_home_url': mainreverse('presale:index'),
        'organizer_link_back': bool(event.settings.get('organizer_link_back')),
    }
    organizer = getattr(event, 'organizer', None)
    if organizer is not None:
        navigation['organizer_name'] = str(organizer.name)
        navigation['organizer_presale_url'] = str(eventreverse(organizer, 'presale:organizer.index'))
    out['navigation'] = navigation
    out['typography'] = build_video_typography_for_event(event)

    return out
