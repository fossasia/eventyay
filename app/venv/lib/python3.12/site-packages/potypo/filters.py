from enchant.tokenize import Filter

def make_EdgecaseFilter(words):
    class EdgecaseFilter(Filter):
        """
        Some words might be special edgecase words that cannot really be
        spellchecked and whose addition to the wordlist doesn't make sense.
        Examples are hyphenated words, since the tokenization will split them
        apart, which it should do, but which will sometimes lead to incorrect
        spellchecks.  Therefore, these have to be skipped it manually beforehand.
        """

        def _skip(self, word):
            if word in words:
                return True
            elif word.lower() in words:
                return True

    return EdgecaseFilter

class HTMLFilter(Filter):
    """
    We don't want to check HTML entities.
    """

    def _skip(self, word):
        if "&lt" in word:
            return True


class PythonFormatFilter(Filter):
    """
    We need to filter the python-format-words such as %(redeemed)s so that they
    don't get spell-checked.
    """
    def _skip(self, word):
        if word[:2] == "%(":
            return True
        if "{" in word:
            return True
        if word[:2] == "#%":
            return True
        return False
