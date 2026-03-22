"""
    python-creole
    ~~~~~~~~~~~~~

    :sourcecode:
      https://github.com/jedie/python-creole

    :PyPi:
      https://pypi.org/project/python-creole/

    :copyleft: 2008-2021 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import warnings

from creole.emitter.creol2html_emitter import HtmlEmitter
from creole.emitter.html2creole_emitter import CreoleEmitter
from creole.emitter.html2rest_emitter import ReStructuredTextEmitter
from creole.emitter.html2textile_emitter import TextileEmitter
from creole.parser.creol2html_parser import CreoleParser
from creole.parser.html_parser import HtmlParser


__version__ = "1.4.10"
__api__ = "1.0"  # Creole 1.0 spec - http://wikicreole.org/

VERSION_STRING = __version__  # remove in future
API_STRING = __api__  # remove in future


def creole2html(markup_string, debug=False,
                parser_kwargs=None, emitter_kwargs=None,
                block_rules=None, blog_line_breaks=True,
                macros=None, verbose=None, stderr=None,
                strict=False,
                ):
    """
    convert creole markup into html code

    >>> creole2html('This is **creole //markup//**!')
    '<p>This is <strong>creole <i>markup</i></strong>!</p>'

    Info: parser_kwargs and emitter_kwargs are deprecated
    """
    assert isinstance(markup_string, str), "given markup_string must be unicode!"

    parser_kwargs2 = {
        "block_rules": block_rules,
        "blog_line_breaks": blog_line_breaks,
        "debug": debug,
    }
    if parser_kwargs is not None:
        warnings.warn(
            "parser_kwargs argument in creole2html would be removed in the future!",
            PendingDeprecationWarning)
        parser_kwargs2.update(parser_kwargs)

    # Create document tree from creole markup
    document = CreoleParser(markup_string, **parser_kwargs2).parse()
    if debug:
        document.debug()

    emitter_kwargs2 = {
        "macros": macros,
        "verbose": verbose,
        "stderr": stderr,
        "strict": strict,
    }
    if emitter_kwargs is not None:
        warnings.warn(
            "emitter_kwargs argument in creole2html would be removed in the future!",
            PendingDeprecationWarning)
        emitter_kwargs2.update(emitter_kwargs)

    # Build html code from document tree
    return HtmlEmitter(document, **emitter_kwargs2).emit()


def parse_html(html_string, debug=False):
    """ create the document tree from html code """
    assert isinstance(html_string, str), "given html_string must be unicode!"

    h2c = HtmlParser(debug=debug)
    document_tree = h2c.feed(html_string)
    if debug:
        h2c.debug()
    return document_tree


def html2creole(
    html_string,
    debug=False,
    parser_kwargs=None,
    emitter_kwargs=None,
    unknown_emit=None,
    strict=False,
):
    """
    convert html code into creole markup

    >>> html2creole('<p>This is <strong>creole <i>markup</i></strong>!</p>')
    'This is **creole //markup//**!'
    """
    if parser_kwargs is not None:
        warnings.warn(
            "parser_kwargs argument in html2creole would be removed in the future!",
            PendingDeprecationWarning)

    document_tree = parse_html(html_string, debug=debug)

    emitter_kwargs2 = {
        "unknown_emit": unknown_emit,
        "strict": strict,
    }
    if emitter_kwargs is not None:
        warnings.warn(
            "emitter_kwargs argument in html2creole would be removed in the future!",
            PendingDeprecationWarning)
        emitter_kwargs2.update(emitter_kwargs)

    # create creole markup from the document tree
    emitter = CreoleEmitter(document_tree, debug=debug, **emitter_kwargs2)
    return emitter.emit()


def html2textile(html_string, debug=False,
                 parser_kwargs=None, emitter_kwargs=None,
                 unknown_emit=None
                 ):
    """
    convert html code into textile markup

    >>> html2textile('<p>This is <strong>textile <i>markup</i></strong>!</p>')
    'This is *textile __markup__*!'
    """
    if parser_kwargs is not None:
        warnings.warn(
            "parser_kwargs argument in html2textile would be removed in the future!",
            PendingDeprecationWarning)

    document_tree = parse_html(html_string, debug=debug)

    emitter_kwargs2 = {
        "unknown_emit": unknown_emit,
    }
    if emitter_kwargs is not None:
        warnings.warn(
            "emitter_kwargs argument in html2textile would be removed in the future!",
            PendingDeprecationWarning)
        emitter_kwargs2.update(emitter_kwargs)

    # create textile markup from the document tree
    emitter = TextileEmitter(document_tree, debug=debug, **emitter_kwargs2)
    return emitter.emit()


def html2rest(html_string, debug=False,
              parser_kwargs=None, emitter_kwargs=None,
              unknown_emit=None
              ):
    """
    convert html code into ReStructuredText markup

    >>> html2rest('<p>This is <strong>ReStructuredText</strong> <em>markup</em>!</p>')
    'This is **ReStructuredText** *markup*!'
    """
    if parser_kwargs is not None:
        warnings.warn("parser_kwargs argument in html2rest would be removed in the future!", PendingDeprecationWarning)

    document_tree = parse_html(html_string, debug=debug)

    emitter_kwargs2 = {
        "unknown_emit": unknown_emit,
    }
    if emitter_kwargs is not None:
        warnings.warn(
            "emitter_kwargs argument in html2rest would be removed in the future!",
            PendingDeprecationWarning)
        emitter_kwargs2.update(emitter_kwargs)

    # create ReStructuredText markup from the document tree
    emitter = ReStructuredTextEmitter(document_tree, debug=debug, **emitter_kwargs2)
    return emitter.emit()
