"""
    :copyleft: 2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import difflib


def unified_diff(old, new, filename=None):
    """
    Return text of unified diff between old and new.
    """
    if filename is None:
        fromfile = 'old'
        tofile = 'new'
    else:
        fromfile = f'old / {filename}'
        tofile = f'new / {filename}'

    if isinstance(old, str) and isinstance(new, str):
        old = old.splitlines(keepends=True)
        new = new.splitlines(keepends=True)

    diff = difflib.unified_diff(old, new, fromfile=fromfile, tofile=tofile)

    text = ''
    for line in diff:
        text += line

        # Work around missing newline (http://bugs.python.org/issue2142).
        if text and not line.endswith('\n'):
            text += 'n\\ No newline at end of file\n'

    return text
