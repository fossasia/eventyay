import pytest

from eventyay.common.text.rich_text import is_empty_rich_text


@pytest.mark.parametrize(
    ('value', 'expected'),
    (
        (None, True),
        ('', True),
        ('   ', True),
        ('<p></p>', True),
        ('<p><br></p>', True),
        ('<p>&nbsp;</p>', True),
        ('<p> </p>', True),
        ('<p>\u200b</p>', True),
        ('\u200b\u200c\ufeff', True),
        ('<p>Hi</p>', False),
        ('Hi', False),
        ('<p>Hi\u200b</p>', False),
    ),
)
def test_is_empty_rich_text(value, expected):
    assert is_empty_rich_text(value) is expected
