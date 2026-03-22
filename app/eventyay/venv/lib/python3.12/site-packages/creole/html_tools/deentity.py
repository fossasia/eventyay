"""
    python-creole utils
    ~~~~~~~~~~~~~~~~~~~


    :copyleft: 2008-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import re
from html import entities


entities_rules = '|'.join([
    r"(&\#(?P<number>\d+);)",
    r"(&\#x(?P<hex>[a-fA-F0-9]+);)",
    r"(&(?P<named>[a-zA-Z]+);)",
])
# print(entities_rules)
entities_regex = re.compile(
    entities_rules, re.VERBOSE | re.UNICODE | re.MULTILINE
)


class Deentity:
    """
    replace html entity

    >>> d = Deentity()
    >>> d.replace_all("-=[&nbsp;&gt;&#62;&#x3E;nice&lt;&#60;&#x3C;&nbsp;]=-")
    '-=[ >>>nice<<< ]=-'

    >>> d.replace_all("-=[M&uuml;hlheim]=-") # uuml - latin small letter u with diaeresis
    '-=[M\\xfchlheim]=-'

    >>> d.replace_number("126")
    '~'
    >>> d.replace_hex("7E")
    '~'
    >>> d.replace_named("amp")
    '&'
    """

    def replace_number(self, text):
        """ unicode number entity """
        unicode_no = int(text)
        return chr(unicode_no)

    def replace_hex(self, text):
        """ hex entity """
        unicode_no = int(text, 16)
        return chr(unicode_no)

    def replace_named(self, text):
        """ named entity """
        if text == "nbsp":
            # Non breaking spaces is not in htmlentitydefs
            return " "
        else:
            codepoint = entities.name2codepoint[text]
            return chr(codepoint)

    def replace_all(self, content):
        """ replace all html entities form the given text. """
        def replace_entity(match):
            groups = match.groupdict()
            for name, text in groups.items():
                if text is not None:
                    replace_method = getattr(self, f'replace_{name}')
                    return replace_method(text)

            # Should never happen:
            raise RuntimeError("deentitfy re rules wrong!")

        return entities_regex.sub(replace_entity, content)


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
