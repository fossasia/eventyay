import pytest

from eventyay.common.text.rich_text import is_empty_rich_text, rich_text_to_plain_text


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


@pytest.mark.parametrize(
    ('value', 'expected'),
    (
        (None, ''),
        ('', ''),
        ('Plain text', 'Plain text'),
        ('Use <Widget> here', 'Use <Widget> here'),
        ('**Markdown** stays as written', '**Markdown** stays as written'),
        ('<p>One</p><p>Two</p>', 'One\n\nTwo'),
        ('<p>Line one<br>Line two</p>', 'Line one\nLine two'),
        ('<p>One<br class="x">Two</p>', 'One\nTwo'),
        ('<ul><li>First</li><li>Second</li></ul>', '- First\n- Second'),
        ('<ul><li><p>First</p></li><li><p>Second</p></li></ul>', '- First\n- Second'),
        ('<ol><li><p>First</p></li><li><p>Second</p></li></ol>', '1. First\n2. Second'),
        ('<ul><li><p>Outer</p><ul><li><p>Inner</p></li></ul></li></ul>', '- Outer\n  - Inner'),
        ('<ul><li title="x>y">First</li></ul>', '- First'),
        ('<p>Intro</p><ul><li>Item</li></ul><p>Outro</p>', 'Intro\n\n- Item\n\nOutro'),
        ('<p>Tom &amp; Jerry&nbsp;rock</p>', 'Tom & Jerry rock'),
        (
            '<p><strong>Bold</strong> and <a href="https://example.com">slides</a></p>',
            'Bold and slides (https://example.com)',
        ),
        ('<p><a href="https://example.com">https://example.com</a></p>', 'https://example.com'),
        ('<p>&lt;Widget&gt; text</p>', '<Widget> text'),
        ('<p></p><p>Text</p><p></p>', 'Text'),
        ('<p><strong>Hello</strong>\n<em>world</em></p>', 'Hello world'),
        ('<p>Wrapped\n   text</p>', 'Wrapped text'),
        ('<ol start="3"><li>Third</li><li>Fourth</li></ol>', '3. Third\n4. Fourth'),
        ('<ul>\n  <li>First</li>\n  <li>Second</li>\n</ul>', '- First\n- Second'),
        ('<table><tr><td>Agenda</td><td>10:00</td></tr><tr><td>Talk</td></tr></table>', 'Agenda 10:00\nTalk'),
        ('<pre>if ready:\n    run()</pre>', 'if ready:\n    run()'),
        ('<p>Intro</p><pre>a\n  b</pre><p>Outro</p>', 'Intro\n\na\n  b\n\nOutro'),
        ('<p>Hi</p><script>alert("x")</script><style>p { color: red; }</style>', 'Hi'),
        ('<ol start="--3"><li>First</li></ol>', '1. First'),
        ('<ol start="\u00b2"><li>First</li></ol>', '1. First'),
        ('<ol start=""><li>First</li></ol>', '1. First'),
        ('If a < b\nthen c', 'If a < b\nthen c'),
        ('x <b and y', 'x <b and y'),
        ('Intro text\n\nUse <a> tags carefully', 'Intro text\n\nUse <a> tags carefully'),
        ('<ul><li><p>Hello</p><p>World</p></li></ul>', '- Hello\nWorld'),
        ('<ul><li><h3>Title</h3><p>Body</p></li></ul>', '- Title\nBody'),
        ('<ol><li><p>A</p><blockquote><p>Quote</p></blockquote></li></ol>', '1. A\nQuote'),
        ('<ul><li><p>Outer</p><ul><li><p>Inner</p></li></ul><p>More</p></li></ul>', '- Outer\n  - Inner\nMore'),
        ('Some text<h2>Heading</h2><p>Body</p>', 'Some text\n\nHeading\n\nBody'),
        ('<p>Line one<br/>Line two</p>', 'Line one\nLine two'),
    ),
)
def test_rich_text_to_plain_text(value, expected):
    assert rich_text_to_plain_text(value) == expected
