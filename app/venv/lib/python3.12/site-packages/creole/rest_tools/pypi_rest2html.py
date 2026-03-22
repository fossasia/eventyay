"""
    Try to be so strict as PyPi.

    Code based on:
    https://bitbucket.org/pypa/pypi/src/tip/description_utils.py

    see also:
    https://bitbucket.org/pypa/pypi/issue/161/rest-formatting-fails-and-there-is-no-way
"""


from urllib.parse import urlparse

from creole.exceptions import DocutilsImportError


try:
    import docutils  # noqa flake8
    from docutils import io, readers
    from docutils.core import Publisher, publish_doctree
    from docutils.transforms import TransformError
except ImportError as err:
    msg = (
        "%s - You can't use rest2html!"
        " Please install: http://pypi.python.org/pypi/docutils"
    ) % err
    raise DocutilsImportError(msg)


ALLOWED_SCHEMES = '''file ftp gopher hdl http https imap mailto mms news nntp
prospero rsync rtsp rtspu sftp shttp sip sips snews svn svn+ssh telnet
wais irc'''.split()


def pypi_rest2html(source, output_encoding='unicode'):
    """
    >>> pypi_rest2html("test!")
    '<p>test!</p>\\n'
    """
    settings_overrides = {
        'raw_enabled': 0,  # no raw HTML code
        'file_insertion_enabled': 0,  # no file/URL access
        'halt_level': 2,  # at warnings or errors, raise an exception
        'report_level': 5,  # never report problems with the reST code
    }

    # Convert reStructuredText to HTML using Docutils.
    document = publish_doctree(source=source,
                               settings_overrides=settings_overrides)

    for node in document.traverse():
        if node.tagname == '#text':
            continue
        if node.hasattr('refuri'):
            uri = node['refuri']
        elif node.hasattr('uri'):
            uri = node['uri']
        else:
            continue
        o = urlparse(uri)
        if o.scheme not in ALLOWED_SCHEMES:
            raise TransformError('link scheme not allowed')

    # now turn the transformed document into HTML
    reader = readers.doctree.Reader(parser_name='null')
    pub = Publisher(reader, source=io.DocTreeInput(document),
                    destination_class=io.StringOutput)
    pub.set_writer('html')
    pub.process_programmatic_settings(None, settings_overrides, None)
    pub.set_destination(None, None)
    pub.publish()
    parts = pub.writer.parts

    output = parts['body']

    if output_encoding != 'unicode':
        output = output.encode(output_encoding)

    return output


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
