import enum


def coalesce(*args):
    '''
    Return the first non-None argument

    >>> coalesce()

    >>> coalesce(0, 1)
    0
    >>> coalesce(None, 0)
    0
    '''

    for arg in args:
        if arg is not None:
            return arg


class Strip(enum.IntEnum):
    NONE = 0
    LEFT = 1
    RIGHT = 2
    BOTH = 3


def join_lines(string, strip=Strip.BOTH):
    '''
    Join strings together and strip whitespace in between if needed
    '''
    lines = []

    for line in string.splitlines():
        if strip & Strip.RIGHT:
            line = line.rstrip()

        if strip & Strip.LEFT:
            line = line.lstrip()

        lines.append(line)

    return ''.join(lines)
