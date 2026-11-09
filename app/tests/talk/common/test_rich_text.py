import pytest

from eventyay.common.text.rich_text import (
    is_empty_rich_text,
    rich_text_to_plain_text,
    rich_text_to_preview_text,
)


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


@pytest.mark.parametrize(
    ('value', 'expected'),
    (
        (None, ''),
        ('', ''),
        ('   ', ''),
        ('Plain text description', 'Plain text description'),
        ('<p>Simple paragraph</p>', 'Simple paragraph'),
        ('<p>First</p><p>Second</p>', 'First Second'),
        ('<p>Line 1<br>Line 2<br/>Line 3</p>', 'Line 1 Line 2 Line 3'),
        ('<p>Text with <strong>bold</strong> and <em>italic</em>.</p>', 'Text with bold and italic.'),
        ('<div><p><span>Deeply <em>nested</em> text</span></p></div>', 'Deeply nested text'),
        ('<p>Visit <a href="https://example.com/very/long/url">Eventyay</a> today!</p>', 'Visit Eventyay today!'),
        ('<ul><li>Item 1</li><li>Item 2</li></ul>', 'Item 1 Item 2'),
        ('<ol><li>First</li><li>Second</li></ol>', 'First Second'),
        ('<table><tr><td>Topic</td><td>Speaker</td></tr></table>', 'Topic Speaker'),
        ('<p>Entities: &amp; &lt; &gt; &quot; &#39; &nbsp; done</p>', 'Entities: & < > " \' done'),
        ('<p>Unclosed <b>nested tags', 'Unclosed nested tags'),
        ('<p>Hi</p><script>alert("x")</script><style>p { color: red; }</style>', 'Hi'),
        ('<script>alert("hello")</script>', ''),
        ('<style>body { background: black; }</style>', ''),
        ('Exploring std::vector<T> with Eventyay', 'Exploring std::vector<T> with Eventyay'),
        ('<p>Multiple   spaces   and\nnewlines</p>', 'Multiple spaces and newlines'),
    ),
)
def test_rich_text_to_preview_text(value, expected):
    assert rich_text_to_preview_text(value) == expected


def test_rich_text_to_preview_text_truncation():
    # Text shorter than max_chars remains untouched
    assert rich_text_to_preview_text('<p>Short text</p>', max_chars=200) == 'Short text'

    # Exactly 200 characters remains untouched without ellipsis
    exact_text = 'A' * 200
    assert rich_text_to_preview_text(f'<p>{exact_text}</p>', max_chars=200) == exact_text

    # 250 characters truncated cleanly to 200 ending with …
    long_raw = '<p>' + ('B' * 250) + '</p>'
    truncated = rich_text_to_preview_text(long_raw, max_chars=200)
    assert len(truncated) == 200
    assert truncated.endswith('…')
    assert truncated == ('B' * 199) + '…'

    # Custom max_chars
    custom_raw = '<p>' + ('C' * 100) + '</p>'
    custom_truncated = rich_text_to_preview_text(custom_raw, max_chars=50)
    assert len(custom_truncated) == 50
    assert custom_truncated == ('C' * 49) + '…'


def test_rich_text_to_preview_text_early_cutoff_preserves_accuracy():
    # 50,000 characters input stops early without runaway parsing
    prefix = '<p>Important session summary here. </p>'
    massive_body = '<p>' + ('Extra information words. ' * 2000) + '</p>'
    result = rich_text_to_preview_text(prefix + massive_body, max_chars=200)
    assert len(result) == 200
    assert result.startswith('Important session summary here.')
    assert result.endswith('…')


def test_rich_text_to_preview_text_early_cutoff_nested_script_style():
    # Very large script and style blocks are discarded completely and never trigger false cutoff
    huge_script = '<script>' + ('var x = 1; ' * 5000) + '</script>'
    huge_style = '<style>' + ('body { margin: 0; } ' * 5000) + '</style>'
    body = '<p>Visible text after large script and style blocks.</p>'
    result = rich_text_to_preview_text(huge_script + huge_style + body, max_chars=200)
    assert result == 'Visible text after large script and style blocks.'
    assert 'var x' not in result
    assert 'margin' not in result


def test_rich_text_to_preview_text_whitespace_cutoff():
    # Large whitespace prefixes followed by > 200 visible characters
    whitespace_prefix = '   \n\t   ' * 200
    visible_body = '<p>' + ('Visible session text. ' * 20) + '</p>'
    result = rich_text_to_preview_text(whitespace_prefix + visible_body, max_chars=200)
    assert len(result) == 200
    assert result.startswith('Visible session text.')
    assert result.endswith('…')

    # Many whitespace-only HTML nodes before visible content
    empty_nodes = '<p>  \n\t </p><div>  </div><span>  </span>' * 50
    result_nodes = rich_text_to_preview_text(empty_nodes + visible_body, max_chars=200)
    assert len(result_nodes) == 200
    assert result_nodes.startswith('Visible session text.')
    assert result_nodes.endswith('…')

    # A single extremely large text node
    huge_text_node = '<p>' + ('Z' * 100000) + '</p>'
    result_huge = rich_text_to_preview_text(huge_text_node, max_chars=200)
    assert len(result_huge) == 200
    assert result_huge == ('Z' * 199) + '…'

    # Normal description that does not require truncation
    normal_text = '<p>A standard short session description.</p>'
    assert rich_text_to_preview_text(normal_text, max_chars=200) == 'A standard short session description.'


@pytest.mark.parametrize(
    ('value', 'expected'),
    (
        ('**bold text**', 'bold text'),
        ('*italic text*', 'italic text'),
        ('[Eventyay Platform](https://eventyay.com)', 'Eventyay Platform'),
        ('`sys.py`', 'sys.py'),
        (
            'Mixed text with **bold**, [Eventyay](https://eventyay.com), and `sys.py`.',
            'Mixed text with bold, Eventyay, and sys.py.',
        ),
        ('Exploring std::vector<T> with Eventyay', 'Exploring std::vector<T> with Eventyay'),
        ('if (a < b)', 'if (a < b)'),
        ('Check __init__.py in Python packages', 'Check __init__.py in Python packages'),
        (
            'Technical in Markdown: **Python** with __init__.py and std::vector<T>',
            'Technical in Markdown: Python with __init__.py and std::vector<T>',
        ),
    ),
)
def test_rich_text_to_preview_text_markdown_and_technical(value, expected):
    assert rich_text_to_preview_text(value) == expected


@pytest.mark.parametrize(
    ('value', 'expected'),
    (
        ('<strong>only bold</strong>', 'only bold'),
        ('<em>only italic</em>', 'only italic'),
        ('<span>only span</span>', 'only span'),
        ('<span>Deeply <strong><em>nested</em></strong> tags</span>', 'Deeply nested tags'),
        ('<span class="badge" data-id="123">Inline with attributes</span>', 'Inline with attributes'),
        (
            '<a href="https://example.com" target="_blank" rel="noopener">Anchor with attributes</a>',
            'Anchor with attributes',
        ),
        ('Technical text: if (a < b) and std::vector<T>', 'Technical text: if (a < b) and std::vector<T>'),
        (
            '<p>Mixed block and <strong>inline</strong> HTML with std::vector<T></p>',
            'Mixed block and inline HTML with std::vector<T>',
        ),
    ),
)
def test_rich_text_to_preview_text_inline_html(value, expected):
    assert rich_text_to_preview_text(value) == expected


@pytest.mark.parametrize(
    ('value', 'expected'),
    (
        ('Hello\u200bWorld\ufeff!', 'HelloWorld!'),
        ('Bidi\u202aLTR\u202bRLO\u202ctest', 'BidiLTRRLOtest'),
        ('Ordinary Unicode: Café, résumé, naïve', 'Ordinary Unicode: Café, résumé, naïve'),
        ('Emoji: 🎉 🚀 🐍', 'Emoji: 🎉 🚀 🐍'),
        ('Hindi: नमस्ते दुनिया और Eventyay', 'Hindi: नमस्ते दुनिया और Eventyay'),
        ('<p>Hindi: नमस्ते <strong>दुनिया</strong> \u200b🎉</p>', 'Hindi: नमस्ते दुनिया 🎉'),
    ),
)
def test_rich_text_to_preview_text_invisible_chars_and_unicode(value, expected):
    assert rich_text_to_preview_text(value) == expected
