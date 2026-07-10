"""Video SPA theme derived from Common Settings plus stored event.config['theme']."""

import re

_VALID_HEX_6 = re.compile(r'^#[0-9a-f]{6}$')


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


def build_video_theme_for_event(event):
    """
    Theme payload for the video SPA injection and world.config.get.

    Navbar/sidebar colors follow Common Settings (primary + page background).
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

    existing_colors = out.get('colors')
    if not isinstance(existing_colors, dict):
        existing_colors = {}
    else:
        existing_colors = {**existing_colors}

    sidebar_text = event.settings.get('video_menu_text_color')
    sidebar_hover = event.settings.get('video_menu_text_hover_color') or event.settings.get('menu_text_scroll_over_color')

    out['colors'] = {
        **existing_colors,
        'primary': primary,
        'sidebar': primary,
        'bbb_background': bbb_bg,
    }
    if sidebar_text:
        out['colors']['sidebarText'] = normalize_video_theme_hex(sidebar_text)
    if sidebar_hover:
        out['colors']['sidebarTextHover'] = normalize_video_theme_hex(sidebar_hover)

    logo = out.get('logo')
    if isinstance(logo, dict):
        logo = {**logo}
    else:
        logo = {}
    visible = event.visible_logo_url
    if visible:
        logo['url'] = visible
    out['logo'] = logo

    return out
