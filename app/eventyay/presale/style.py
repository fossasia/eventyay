import hashlib
import logging
import os
from urllib.parse import urljoin, urlsplit

import django_libsass
import sass
from compressor.filters.cssmin import CSSCompressorFilter
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Count
from django.dispatch import Signal
from django.templatetags.static import static as _static
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event, Event_SettingsStore, Organizer
from eventyay.base.services.tasks import (
    TransactionAwareProfiledEventTask,
    TransactionAwareTask,
)
from eventyay.celery_app import app
from eventyay.multidomain.urlreverse import (
    get_event_domain,
    get_organizer_domain,
)
from eventyay.presale.signals import sass_postamble, sass_preamble


logger = logging.getLogger('eventyay.presale.style')
affected_keys = [
    'primary_font',
    'primary_color',
    'theme_color_success',
    'theme_color_danger',
]

BASE_SANS_STACK = '"Open Sans", "OpenSans", "Helvetica Neue", Helvetica, Arial, sans-serif'

SYSTEM_FONTS = {
    'Open Sans': BASE_SANS_STACK,
    'System-UI': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol"',
    'Arial': 'Arial, "Helvetica Neue", Helvetica, sans-serif',
    'Helvetica': '"Helvetica Neue", Helvetica, Arial, sans-serif',
    'Georgia': 'Georgia, Cambria, "Times New Roman", Times, serif',
    'Verdana': 'Verdana, Geneva, sans-serif',
    'Times New Roman': '"Times New Roman", Times, Baskerville, Georgia, serif',
    'Trebuchet MS': '"Trebuchet MS", "Lucida Grande", "Lucida Sans Unicode", "Lucida Sans", Tahoma, sans-serif',
    'Courier New': '"Courier New", Courier, monospace',
}

SYSTEM_FONT_CHOICES = [
    (font_key, 'System UI (Default Stack)' if font_key == 'System-UI' else font_key)
    for font_key in SYSTEM_FONTS.keys()
]


def compile_scss(object, file='main.scss', fonts=True):
    sassdir = os.path.join(settings.STATIC_ROOT, 'pretixpresale/scss')

    def static(path):
        sp = _static(path)
        if not settings.MEDIA_URL.startswith('/') and sp.startswith('/'):
            if isinstance(object, Event):
                domain = get_event_domain(object, fallback=True)
            else:
                domain = get_organizer_domain(object)
            if domain:
                siteurlsplit = urlsplit(settings.SITE_URL)
                if siteurlsplit.port and siteurlsplit.port not in (80, 443):
                    domain = '%s:%d' % (domain, siteurlsplit.port)
                sp = urljoin('%s://%s' % (siteurlsplit.scheme, domain), sp)
            else:
                sp = urljoin(settings.SITE_URL, sp)
        return f'"{sp}"'

    sassrules = []
    if object.settings.get('primary_color'):
        sassrules.append('$brand-primary: {};'.format(object.settings.get('primary_color')))
    if object.settings.get('theme_color_success'):
        sassrules.append('$brand-success: {};'.format(object.settings.get('theme_color_success')))
    if object.settings.get('theme_color_danger'):
        sassrules.append('$brand-danger: {};'.format(object.settings.get('theme_color_danger')))
    if object.settings.get('theme_color_background'):
        sassrules.append('$body-bg: {};'.format(object.settings.get('theme_color_background')))
    if object.settings.get('hover_button_color'):
        sassrules.append('$hover-button-color: {};'.format(object.settings.get('hover_button_color')))
    if not object.settings.get('theme_round_borders'):
        sassrules.append('$border-radius-base: 0;')
        sassrules.append('$border-radius-large: 0;')
        sassrules.append('$border-radius-small: 0;')

    font_family_value = None
    if fonts:
        fonts_dict = get_fonts()
        resolved_font, font_family_value = resolve_font(object, fonts_dict=fonts_dict)
        if font_family_value:
            if resolved_font in SYSTEM_FONTS:
                # We explicitly do not use !default here because we want to override
                # any default variables declared in Bootstrap/our stylesheets.
                sassrules.append(
                    f'$font-family-sans-serif: {font_family_value};'
                )
            elif resolved_font in fonts_dict:
                sassrules.append(get_font_stylesheet(resolved_font, fonts=fonts_dict, for_sass=True))
                # We explicitly do not use !default here because we want to override
                # any default variables declared in Bootstrap/our stylesheets.
                sassrules.append(
                    f'$font-family-sans-serif: {font_family_value};'
                )
            else:
                # Fallback for old or invalid font values: treat as Open Sans
                sassrules.append(
                    f'$font-family-sans-serif: {font_family_value};'
                )

    if isinstance(object, Event):
        for recv, resp in sass_preamble.send(object, filename=file):
            sassrules.append(resp)

    sassrules.append(f'@import "{file}";')

    # Override the --font-family CSS custom property defined in _fonts.css.
    # That file sets body { font-family: var(--font-family) } and is loaded
    # outside the compiled SCSS, so it wins over $font-family-sans-serif.
    # Injecting :root { --font-family: ... } after the @import ensures our
    # font choice takes precedence via source order.
    if font_family_value:
        sassrules.append(
            f':root {{ --font-family: {font_family_value}; --font-family-title: {font_family_value}; }}'
        )

    if isinstance(object, Event):
        for recv, resp in sass_postamble.send(object, filename=file):
            sassrules.append(resp)

    sasssrc = '\n'.join(sassrules)

    srcchecksum = hashlib.sha1(sasssrc.encode('utf-8')).hexdigest()

    cp = cache.get_or_set('sass_compile_prefix', now().isoformat())
    css = cache.get(f'sass_compile_{cp}_{srcchecksum}')
    if not css:
        cf = dict(django_libsass.CUSTOM_FUNCTIONS)
        cf['static'] = static
        css = sass.compile(
            string=sasssrc,
            include_paths=[sassdir],
            output_style='nested',
            custom_functions=cf,
        )
        cssf = CSSCompressorFilter(css)
        css = cssf.output()
        cache.set(f'sass_compile_{cp}_{srcchecksum}', css, 600)

    checksum = hashlib.sha1(css.encode('utf-8')).hexdigest()
    return css, checksum


@app.task(base=TransactionAwareProfiledEventTask)
def regenerate_css(event):
    # main.scss
    css, checksum = compile_scss(event)
    fname = f'pub/{event.organizer.slug}/{event.slug}/presale.{checksum[:16]}.css'

    if event.settings.get('presale_css_checksum', '') != checksum:
        newname = default_storage.save(fname, ContentFile(css.encode('utf-8')))
        event.settings.set('presale_css_file', newname)
        event.settings.set('presale_css_checksum', checksum)

    # widget.scss
    css, checksum = compile_scss(event, file='widget.scss', fonts=False)
    fname = f'pub/{event.organizer.slug}/{event.slug}/widget.{checksum[:16]}.css'

    if event.settings.get('presale_widget_css_checksum', '') != checksum:
        newname = default_storage.save(fname, ContentFile(css.encode('utf-8')))
        event.settings.set('presale_widget_css_file', newname)
        event.settings.set('presale_widget_css_checksum', checksum)


@app.task(base=TransactionAwareTask)
def regenerate_organizer_css(organizer_id: int):
    organizer = Organizer.objects.get(pk=organizer_id)

    with scope(organizer=organizer):
        # main.scss
        css, checksum = compile_scss(organizer)
        fname = f'pub/{organizer.slug}/presale.{checksum[:16]}.css'
        if organizer.settings.get('presale_css_checksum', '') != checksum:
            newname = default_storage.save(fname, ContentFile(css.encode('utf-8')))
            organizer.settings.set('presale_css_file', newname)
            organizer.settings.set('presale_css_checksum', checksum)

        # widget.scss
        css, checksum = compile_scss(organizer, file='widget.scss', fonts=False)
        fname = f'pub/{organizer.slug}/widget.{checksum[:16]}.css'
        if organizer.settings.get('presale_widget_css_checksum', '') != checksum:
            newname = default_storage.save(fname, ContentFile(css.encode('utf-8')))
            organizer.settings.set('presale_widget_css_file', newname)
            organizer.settings.set('presale_widget_css_checksum', checksum)

        fully_overridden_events = set(
            Event_SettingsStore.objects.filter(
                object__organizer=organizer, key__in=affected_keys
            ).exclude(value__in=['', '""', "''"]).values('object_id').annotate(
                overridden_count=Count('key')
            ).filter(
                overridden_count=len(affected_keys)
            ).values_list('object_id', flat=True)
        )
        for event in organizer.events.all():
            if event.pk not in fully_overridden_events:
                event.settings.flush()
                regenerate_css.apply_async(args=(event.pk,))


register_fonts = Signal()
"""
Return a dictionaries of the following structure. Paths should be relative to static root.

{
    "font name": {
        "regular": {
            "truetype": "….ttf",
            "woff": "…",
            "woff2": "…"
        },
        "bold": {
            ...
        },
        "italic": {
            ...
        },
        "bolditalic": {
            ...
        }
    }
}
"""


def resolve_font(object, fonts_dict=None):
    font = object.settings.get('primary_font')
    if not font and isinstance(object, Event) and hasattr(object, 'organizer'):
        font = object.organizer.settings.get('primary_font')

    if not font:
        return None, None

    if font in SYSTEM_FONTS:
        return font, SYSTEM_FONTS[font]

    if fonts_dict is None:
        fonts_dict = get_fonts()

    if font in fonts_dict:
        escaped_font = escape_font_name(font)
        return font, f'"{escaped_font}", {BASE_SANS_STACK}'
    else:
        return 'Open Sans', SYSTEM_FONTS['Open Sans']


def get_fonts():
    f = {}
    for recv, value in register_fonts.send(0):
        f.update(value)
    return f


def escape_font_name(font_name):
    if not font_name:
        return ''
    # Escape backslashes first, then escape double quotes.
    # Also strip out characters that shouldn't be in a font name, like newlines, semicolons, and curly braces.
    escaped = font_name.replace('\\', '\\\\').replace('"', '\\"')
    for char in (';', '{', '}', '\r', '\n'):
        escaped = escaped.replace(char, '')
    return escaped


def get_font_stylesheet(font_name, fonts=None, for_sass=True):
    stylesheet = []
    if fonts is None:
        fonts = get_fonts()
    font = fonts[font_name]
    escaped_font_name = escape_font_name(font_name)
    for sty, formats in font.items():
        if sty == 'sample':
            continue
        stylesheet.append('@font-face { ')
        stylesheet.append(f'font-family: "{escaped_font_name}";')
        if sty in ('italic', 'bolditalic'):
            stylesheet.append('font-style: italic;')
        else:
            stylesheet.append('font-style: normal;')
        if sty in ('bold', 'bolditalic'):
            stylesheet.append('font-weight: bold;')
        else:
            stylesheet.append('font-weight: normal;')

        srcs = []
        if for_sass:
            if 'woff2' in formats:
                srcs.append("url(static('{}')) format('woff2')".format(formats['woff2']))
            if 'woff' in formats:
                srcs.append("url(static('{}')) format('woff')".format(formats['woff']))
            if 'truetype' in formats:
                srcs.append("url(static('{}')) format('truetype')".format(formats['truetype']))
        else:
            if 'woff2' in formats:
                srcs.append("url('{}') format('woff2')".format(_static(formats['woff2'])))
            if 'woff' in formats:
                srcs.append("url('{}') format('woff')".format(_static(formats['woff'])))
            if 'truetype' in formats:
                srcs.append("url('{}') format('truetype')".format(_static(formats['truetype'])))
        stylesheet.append('src: {};'.format(', '.join(srcs)))
        stylesheet.append('font-display: swap;')
        stylesheet.append('}')
    return '\n'.join(stylesheet)
