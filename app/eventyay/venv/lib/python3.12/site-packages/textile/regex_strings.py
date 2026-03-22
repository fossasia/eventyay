# -*- coding: utf-8 -*-
try:
    # Use regex module for matching uppercase characters if installed,
    # otherwise fall back to finding all the uppercase chars in a loop.
    import regex as re  # noqa: F401
    upper_re_s = r'\p{Lu}'
    regex_snippets = {
        'acr': r'\p{Lu}\p{Nd}',
        'abr': r'\p{Lu}',
        'nab': r'\p{Ll}',
        'wrd': r'(?:\p{L}|\p{M}|\p{N}|\p{Pc})',
        'cur': r'\p{Sc}',
        'digit': r'\p{N}',
        'space': r'(?:\p{Zs}|\v)',
        'char': r'(?:[^\p{Zs}\v])',
    }
except ImportError:
    from sys import maxunicode
    upper_re_s = "".join(
        [chr(c) for c in range(maxunicode) if chr(c).isupper()]
    )
    regex_snippets = {
        'acr': r'{0}0-9'.format(upper_re_s),
        'abr': r'{0}'.format(upper_re_s),
        'nab': r'a-z',
        'wrd': r'\w',
        # All codepoints identified as currency symbols
        # by the [mrab-regex library](https://pypi.org/project/regex/)
        # and the UNICODE standard.
        'cur': r'$¢-¥֏؋৲৳৻૱௹฿៛\u20a0-\u20cf\ua838﷼﹩＄￠￡￥￦',
        'digit': r'\d',
        'space': r'(?:\s|\v)',
        'char': r'\S',
    }

halign_re_s = r'(?:\<(?!>)|(?<!<)\>|\<\>|\=|[()]+(?! ))'
valign_re_s = r'[\-^~]'
class_re_s = r'(?:\([^)\n]+\))'       # Don't allow classes/ids,
language_re_s = r'(?:\[[^\]\n]+\])'   # languages,
style_re_s = r'(?:\{[^}\n]+\})'       # or styles to span across newlines
colspan_re_s = r'(?:\\\d+)'
rowspan_re_s = r'(?:\/\d+)'
align_re_s = r'(?:{0}|{1})*'.format(halign_re_s, valign_re_s)
table_span_re_s = r'(?:{0}|{1})*'.format(colspan_re_s, rowspan_re_s)
# regex string to match class, style and language attributes
cls_re_s = (r'(?:'
            r'{c}(?:{l}(?:{s})?|{s}(?:{l})?)?|'
            r'{l}(?:{c}(?:{s})?|{s}(?:{c})?)?|'
            r'{s}(?:{c}(?:{l})?|{l}(?:{c})?)?'
            r')?'
            ).format(c=class_re_s, s=style_re_s, l=language_re_s)
pnct_re_s = r'[-!"#$%&()*+,/:;<=>?@\'\[\\\]\.^_`{|}~]'
syms_re_s = '¤§µ¶†‡•∗∴◊♠♣♥♦'
