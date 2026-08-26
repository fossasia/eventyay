"""Vendor and generated trees that Django gettext should not scan."""

from collections.abc import Iterable, Sequence

LOCALE_IGNORE_PATTERNS = (
    'node_modules',
    'dist',
    'build',
    'compiled-frontend',
    'eventyay/webapp/*',
    'eventyay/static/jsi18n/*',
    'eventyay/static/rrule/*',
    'eventyay/static/vendored/*',
)

# compilemessages walks the whole tree. makemessages already skips
# dot-directories via Django's default .* pattern; compilemessages does not.
COMPILE_IGNORE_PATTERNS = LOCALE_IGNORE_PATTERNS + (
    '.venv',
    'venv',
    'site-packages',
)

SOURCE_LANGUAGE = 'en'


def merge_ignore_patterns(
    ignore_patterns: Iterable[str] | None,
    extra: Sequence[str] = LOCALE_IGNORE_PATTERNS,
) -> list[str]:
    merged = list(ignore_patterns or [])
    for pattern in extra:
        if pattern not in merged:
            merged.append(pattern)
    return merged


def apply_makemessages_defaults(options):
    options['ignore_patterns'] = merge_ignore_patterns(options.get('ignore_patterns'))
    options['keep_pot'] = True
    locale = options.get('locale') or []
    if not locale and not options.get('all'):
        options['all'] = True
    if options.get('all'):
        exclude = list(options.get('exclude') or [])
        if SOURCE_LANGUAGE not in exclude:
            exclude.append(SOURCE_LANGUAGE)
        options['exclude'] = exclude
    return options
