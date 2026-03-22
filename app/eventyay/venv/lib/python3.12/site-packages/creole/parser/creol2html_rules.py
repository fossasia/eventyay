"""
    Creole Rules for parser
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2008-2013 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import re


class InlineRules:
    """
    All inline rules
    """
    proto = r'http|https|ftp|nntp|news|mailto|telnet|file|irc'
    # New regex for finding uris, requires uri to free stand within whitespace or lineends.
    url = r'''(?P<url>
            (^ | (?<=\s))
            (?P<escaped_url>~)?
            (?P<url_target> (?P<url_proto> %s )://[^$\s]+ )
        )''' % proto
    # Original uri matching regex inherited from MoinMoin code.
    # url = r'''(?P<url>
    # (^ | (?<=\s | [.,:;!?()/=]))
    # (?P<escaped_url>~)?
    # (?P<url_target> (?P<url_proto> %s ):\S+? )
    # ($ | (?=\s | [,.:;!?()] (\s | $)))
    # )''' % proto
    link = r'''(?P<link>
            \[\[
            (?P<link_target>.+?) \s*
            ([|] \s* (?P<link_text>.+?) \s*)?
            ]]
        )'''

#    link = r'''(?P<link1>
#            \[\[
#            (?P<link_target1>.+?)\|(?P<link_text1>.+?)
#            ]]
#        )|(?P<link2>
#            \[\[
#            (?P<link_target2> (%s)://[^ ]+) \s* (?P<link_text2>.+?)
#            ]]
#        )|
#            \[\[(?P<internal_link>.+)\]\]
#        ''' % proto

    # image tag
    image = r'''(?P<image>
            {{
            (?P<image_target>.+?) \s*
            (\| \s* (?P<image_text>.+?) \s*)?
            }}
        )'''
    # --------------------------------------------------------------------------

    # a macro like: <<macro>>text<</macro>>
    macro_inline = r'''
        (?P<macro_inline>
        << \s* (?P<macro_inline_start>\w+) \s* (?P<macro_inline_args>.*?) \s* >>
        (?P<macro_inline_text>(.|\n)*?)
        <</ \s* (?P=macro_inline_start) \s* >>
        )
    '''
    # A single macro tag, like <<macro-a foo="bar">> or <<macro />>
    macro_tag = r'''(?P<macro_tag>
            <<(?P<macro_tag_name> \w+) (?P<macro_tag_args>.*?) \s* /*>>
        )'''

    pre_inline = r'(?P<pre_inline> {{{ (?P<pre_inline_text>.*?) }}} )'

    # Basic text typefaces:

    emphasis = r'(?P<emphasis>(?<!:)// (?P<emphasis_text>.+?) (?<!:)// )'
    # there must be no : in front of the // avoids italic rendering
    # in urls with unknown protocols

    strong = r'(?P<strong>\*\* (?P<strong_text>.+?) \*\* )'

    # Creole 1.0 optional:
    monospace = r'(?P<monospace> \#\# (?P<monospace_text>.+?) \#\# )'
    superscript = r'(?P<superscript> \^\^ (?P<superscript_text>.+?) \^\^ )'
    subscript = r'(?P<subscript> ,, (?P<subscript_text>.+?) ,, )'
    underline = r'(?P<underline> __ (?P<underline_text>.+?) __ )'
    delete = r'(?P<delete> ~~ (?P<delete_text>.+?) ~~ )'

    # own additions:
    small = r'(?P<small>-- (?P<small_text>.+?) -- )'

    linebreak = r'(?P<linebreak> \\\\ )'
    escape = r'(?P<escape> ~ (?P<escaped_char>\S) )'
    char = r'(?P<char> . )'


class BlockRules:
    """
    All used block rules.
    """
#    macro_block = r'''(?P<macro_block>
#            \s* << (?P<macro_block_start>\w+) \s* (?P<macro_block_args>.*?) >>
#            (?P<macro_block_text>(.|\n)+?)
#            <</(?P=macro_block_start)>> \s*
#        )'''
#    macro_block = r'''(?P<macro_block>
#            <<(?P<macro_block_start>.*?)>>
#            (?P<macro_block_text>.*?)
#            <</.*?>>
#        )'''

    macro_block = r'''
        (?P<macro_block>
        << \s* (?P<macro_block_start>\w+) \s* (?P<macro_block_args>.*?) \s* >>
        (?P<macro_block_text>(.|\n)*?)
        <</ \s* (?P=macro_block_start) \s* >>
        )
    '''

    line = r'''(?P<line> ^\s*$ )'''  # empty line that separates paragraphs

    head = r'''(?P<head>
        ^
        (?P<head_head>=+) \s*
        (?P<head_text> .*? )
        (=|\s)*?$
    )'''
    separator = r'(?P<separator> ^ \s* ----) [ \t]* $'  # horizontal line

    pre_block = r'''(?P<pre_block>
            ^{{{ \s* $
            (?P<pre_block_text>
                ([\#]!(?P<pre_block_kind>\w*?)(\s+.*)?$)?
                (.|\n)+?
            )
            ^}}})
        '''

    # Matches the whole list, separate items are parsed later.
    # The list *must* start with a single bullet.
    list = r'''(?P<list>
        ^ \s* ([*][^*\#]|[\#][^\#*]).* $
        ( \n[ \t]* [*\#]+.* $ )*
    )'''

    table = r'''^ \s*(?P<table>
            [|].*? \s*
            [|]?
        ) \s* $'''

    re_flags = re.VERBOSE | re.UNICODE | re.MULTILINE

    def __init__(self, blog_line_breaks=True):
        if blog_line_breaks:
            # use blog style line breaks (every line break would be converted into <br />)
            self.text = r'(?P<text> .+ ) (?P<break> (?<!\\)$\n(?!\s*$) )?'
        else:
            # use wiki style line breaks, seperate lines with one space
            self.text = r'(?P<space> (?<!\\)$\n(?!\s*$) )? (?P<text> .+ )'

        self.rules = (
            self.macro_block,
            self.line, self.head, self.separator,
            self.pre_block, self.list,
            self.table, self.text,
        )


class SpecialRules:
    """
    re rules witch not directly used as inline/block rules.
    """
    # Matches single list items:
    item = r'''^ \s* (?P<item>
        (?P<item_head> [\#*]+) \s*
        (?P<item_text> .*?)
    ) \s* $'''

    # For splitting table cells:
    cell = r'''
            \| \s*
            (
                (?P<head> [=][^|]+ ) |
                (?P<cell> (  %s | [^|])+ )
            ) \s*
        ''' % '|'.join([
        InlineRules.link,
        InlineRules.macro_inline, InlineRules.macro_tag,
        InlineRules.image,
        InlineRules.pre_inline
    ])

    # For pre escaping, in creole 1.0 done with ~:
    pre_escape = r' ^(?P<indent>\s*) ~ (?P<rest> \}\}\} \s*) $'


INLINE_FLAGS = re.VERBOSE | re.UNICODE
INLINE_RULES = (
    InlineRules.link, InlineRules.url,
    InlineRules.macro_inline, InlineRules.macro_tag,
    InlineRules.pre_inline, InlineRules.image,

    InlineRules.strong, InlineRules.emphasis,
    InlineRules.monospace, InlineRules.underline,
    InlineRules.superscript, InlineRules.subscript,
    InlineRules.small, InlineRules.delete,

    InlineRules.linebreak,
    InlineRules.escape, InlineRules.char
)


def _verify_rules(rules, flags):
    """
    Simple verify the rules -> try to compile it ;)

    >>> _verify_rules(INLINE_RULES, INLINE_FLAGS)
    Rule test ok.

    >>> block_rules = BlockRules()
    >>> _verify_rules(block_rules.rules, block_rules.re_flags)
    Rule test ok.
    """
    # Test with re.compile
    rule_list = []
    for rule in rules:
        try:
            #            print(rule)
            re.compile(rule, flags)

            # Try to merge the rules. e.g. Check if group named double used.
            rule_list.append(rule)
            re.compile('|'.join(rule_list), flags)
        except Exception:
            print(" *** Error with rule:")
            print(rule)
            print(" -" * 39)
            raise
    print("Rule test ok.")


if __name__ == "__main__":
    import doctest
    print(doctest.testmod())

    print("-" * 80)
