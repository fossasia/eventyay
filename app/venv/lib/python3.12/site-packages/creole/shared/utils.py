"""
    python creole utilities
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2011-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import json
import shlex


try:
    from pygments import lexers
    from pygments.formatters import HtmlFormatter
    PYGMENTS = True
except ImportError:
    PYGMENTS = False


# For string2dict()
KEYWORD_MAP = {
    "True": True,
    "False": False,
    "None": None,
}


def string2dict(raw_content):
    """
    convert a string into a dictionary. e.g.:

    >>> string2dict('key="value"')
    {'key': 'value'}

    >>> string2dict('key1="value1" key2="value2"') == {'key2': 'value2', 'key1': 'value1'}
    True

    See test_creole2html.TestString2Dict()
    """
    parts = shlex.split(raw_content)

    result = {}
    for part in parts:
        key, value = part.split("=", 1)

        if value in KEYWORD_MAP:
            # True False or None
            value = KEYWORD_MAP[value]
        else:
            # A number?
            try:
                value = int(value.strip("'\""))
            except ValueError:
                pass

        result[key] = value

    return result


def dict2string(d):
    """
    FIXME: Find a better was to do this.

    >>> dict2string({'foo':"bar", "no":123})
    'foo="bar" no=123'

    >>> dict2string({"foo":'bar', "no":"ABC"})
    'foo="bar" no="ABC"'

    See test_creole2html.TestDict2String()
    """
    attr_list = []
    for key, value in sorted(d.items()):
        value_string = json.dumps(value)
        attr_list.append(f"{key}={value_string}")
    return " ".join(attr_list)


def get_pygments_formatter():
    if PYGMENTS:
        return HtmlFormatter(lineos=True, encoding='utf-8',
                             style='colorful', outencoding='utf-8',
                             cssclass='pygments')


def get_pygments_lexer(source_type, code):
    if PYGMENTS:
        try:
            return lexers.get_lexer_by_name(source_type)
        except BaseException:
            return lexers.guess_lexer(code)
    else:
        return None


if __name__ == "__main__":
    import doctest
    print(doctest.testmod())
