import re

# In priority order: an existing {{ or }} escape, a {placeholder} slot (with the optional !conversion and
# :format_spec that str.format_map allows), then any other single brace.
# Markdown editors may escape underscores, so {join\_online\_event} still counts as a placeholder.
TEMPLATE_TOKEN = re.compile(
    r'\{\{|\}\}'
    r'|\{[A-Za-z_](?:[A-Za-z0-9_]|\\_)*(?:![rsa])?(?::(?P<format_spec>[^{}]*))?\}'
    r'|[{}]'
)


def is_placeholder(match: re.Match[str]) -> bool:
    if len(match.group()) <= 2:
        return False
    format_spec = match.group('format_spec')
    if format_spec is None:
        return True
    # Mail context values are strings, so a spec a string cannot take (e.g. "{note: see below}")
    # would raise ValueError in format_map. Such text is not a placeholder.
    try:
        format('', format_spec)
    except ValueError:
        return False
    return True


def escape_stray_braces(template: str) -> str:
    """Double every brace that is not a ``{placeholder}`` or an existing ``{{``/``}}`` escape.

    Organizers type braces as plain text (``"{"``, ``{}``, ``See you :}``). ``str.format_map`` raises
    ``ValueError`` on those, so they are escaped here and render literally. Placeholders with a valid
    format spec, such as ``{name:>5}``, are kept.
    """

    def replace(match: re.Match[str]) -> str:
        token = match.group()
        if len(token) == 2 or is_placeholder(match):
            return token
        if len(token) == 1:
            return token * 2
        return '{{' + token[1:-1] + '}}'

    return TEMPLATE_TOKEN.sub(replace, template)


def find_placeholders(template: str) -> list[str]:
    """Return the ``{placeholder}`` slots ``escape_stray_braces`` keeps, with markdown escapes removed."""
    return [match.group().replace('\\_', '_') for match in TEMPLATE_TOKEN.finditer(template) if is_placeholder(match)]
