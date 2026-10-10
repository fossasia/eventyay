import re

# In priority order: an existing {{ or }} escape, a {placeholder} slot, then any other single brace.
# Markdown editors may escape underscores, so {join\_online\_event} still counts as a placeholder.
TEMPLATE_TOKEN = re.compile(r'\{\{|\}\}|\{[A-Za-z_](?:[A-Za-z0-9_]|\\_)*\}|[{}]')


def escape_stray_braces(template: str) -> str:
    """Double every brace that is not a ``{placeholder}`` or an existing ``{{``/``}}`` escape.

    Organizers type braces as plain text (``"{"``, ``{}``, ``See you :}``). ``str.format_map`` raises
    ``ValueError`` on those, so they are escaped here and render literally.
    """
    return TEMPLATE_TOKEN.sub(lambda match: match.group() * 2 if len(match.group()) == 1 else match.group(), template)


def find_placeholders(template: str) -> list[str]:
    """Return the ``{placeholder}`` slots ``escape_stray_braces`` keeps, with markdown escapes removed."""
    # Longer than two characters: skips {{, }} and single braces, which are literal text.
    return [token.replace('\\_', '_') for token in TEMPLATE_TOKEN.findall(template) if len(token) > 2]
