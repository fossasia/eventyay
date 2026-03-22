"""
This is a Python 3 implementation of the Unicode Collation Algorithm (UCA)

It passes 100% of the UCA conformances tests for Unicode 6.3.0 with a
variable-weighting setting of Non-ignorable.

Usage example:

    from pyuca import Collator
    c = Collator()

    sorted_words = sorted(words, key=c.sort_key)

Collator can also take an optional filename for specifying a custom collation
element table.
"""

from .collator import Collator  # noqa
