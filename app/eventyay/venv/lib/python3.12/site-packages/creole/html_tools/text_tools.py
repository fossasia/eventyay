"""
    python-creole utils
    ~~~~~~~~~~~~~~~~~~~


    :copyleft: 2008-2011 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import re


space_re = re.compile(r"^(\s*)(.*?)(\s*)$", re.DOTALL)


def clean_whitespace(txt):
    """
    Special whitespaces cleanup

    >>> clean_whitespace("\\n\\nfoo bar\\n\\n")
    'foo bar\\n'

    >>> clean_whitespace("   foo bar  \\n  \\n")
    ' foo bar\\n'

    >>> clean_whitespace(" \\n \\n  foo bar   ")
    ' foo bar '

    >>> clean_whitespace("foo   bar")
    'foo   bar'
    """
    def cleanup(match):
        start, txt, end = match.groups()

        if " " in start:
            start = " "
        else:
            start = ""

        if "\n" in end:
            end = "\n"
        elif " " in end:
            end = " "

        return start + txt + end

    return space_re.sub(cleanup, txt)


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
