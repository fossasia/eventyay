"""
    python-creole commandline interface
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2013-2020 by the python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import argparse
import codecs

from creole import VERSION_STRING, creole2html, html2creole, html2rest, html2textile


class CreoleCLI:
    def __init__(self, convert_func):
        self.convert_func = convert_func
        self.parser = argparse.ArgumentParser(
            description=(
                "python-creole is an open-source (GPL) markup converter"
                " in pure Python for:"
                " creole2html, html2creole, html2ReSt, html2textile"
            ),
        )
        self.parser.add_argument(
            '--version', action='version',
            version='%%(prog)s from python-creole v%s' % VERSION_STRING  # noqa flynt
        )
        self.parser.add_argument("sourcefile", help="source file to convert")
        self.parser.add_argument("destination", help="Output filename")
        self.parser.add_argument("--encoding",
                                 default="utf-8",
                                 help="Codec for read/write file (default encoding: utf-8)"
                                 )

        args = self.parser.parse_args()

        sourcefile = args.sourcefile
        destination = args.destination
        encoding = args.encoding

        self.convert(sourcefile, destination, encoding)

    def convert(self, sourcefile, destination, encoding):
        print(f"Convert {sourcefile!r} to {destination!r} with {self.convert_func.__name__} (codec: {encoding})")

        with codecs.open(sourcefile, "r", encoding=encoding) as infile:
            with codecs.open(destination, "w", encoding=encoding) as outfile:
                content = infile.read()
                converted = self.convert_func(content)
                outfile.write(converted)
        print(f"done. {destination!r} created.")


def cli_creole2html():
    CreoleCLI(creole2html)


def cli_html2creole():
    CreoleCLI(html2creole)


def cli_html2rest():
    CreoleCLI(html2rest)


def cli_html2textile():
    CreoleCLI(html2textile)


if __name__ == "__main__":
    import sys
    sys.argv += ["../README.creole", "../test.html"]
    print(sys.argv)
    cli_creole2html()
