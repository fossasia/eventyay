"""
    Creole macros
    ~~~~~~~~~~~~~

    Note: all mecro functions must return unicode!

    :copyleft: 2008-2014 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.

"""


from xml.sax.saxutils import escape

from creole.shared.utils import get_pygments_formatter, get_pygments_lexer


try:
    from pygments import highlight
    PYGMENTS = True
except ImportError:
    PYGMENTS = False


def html(text):
    """
    Macro tag <<html>>...<</html>>
    Pass-trought for html code (or other stuff)
    """
    return text


def pre(text):
    """
    Macro tag <<pre>>...<</pre>>.
    Put text between html pre tag.
    """
    return f'<pre>{escape(text)}</pre>'


def code(ext, text):
    """
    Macro tag <<code ext=".some_extension">>...<</code>>
    If pygments is present, highlight the text according to the extension.
    """
    if not PYGMENTS:
        return pre(text)

    try:
        source_type = ''
        if '.' in ext:
            source_type = ext.strip().split('.')[1]
        else:
            source_type = ext.strip()
    except IndexError:
        source_type = ''

    lexer = get_pygments_lexer(source_type, code)
    formatter = get_pygments_formatter()

    try:
        highlighted_text = highlight(text, lexer, formatter).decode('utf-8')
    except BaseException:
        highlighted_text = pre(text)
    finally:
        return highlighted_text.replace('\n', '<br />\n')
