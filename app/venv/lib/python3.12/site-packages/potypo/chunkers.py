from enchant.tokenize import Chunker

def make_PhraseChunker(phrases):
    class PhraseChunker(Chunker):
        """
        It may happen that certain phrases are used in a context that would mark
        them as being incorrectly spelled. We chunk everything but those phrases to
        ignore them.

        The algorithm find the first index at which a phrase starts. In the case of
        multiple phrases, that is the first occurrence of any phrase. It returns
        everything before that phrase and continues with the text after that
        phrase.
        """

        def next(self):
            text = self._text
            offset = self.offset

            if offset >= len(text):
                raise StopIteration

            haystack = text[offset:].tounicode()

            needle = None
            index = None
            for p in phrases:
                try:
                   found = haystack.index(p)
                except ValueError:
                    continue
                if index is None or found < index:
                    index = found
                    needle = p

            if index is None:
                self.set_offset(len(text))
                return (text[offset:], offset)

            self.set_offset(index + len(needle))
            return (text[offset:index], offset)
    return PhraseChunker
