import argparse
import sys
import textile


def main():
    """A CLI tool in the style of python's json.tool.  In fact, this is mostly
    copied directly from that module.  This allows us to create a stand-alone
    tool as well as invoking it via `python -m textile`."""
    prog = 'textile'
    description = ('A simple command line interface for textile module '
                   'to convert textile input to HTML output.  This script '
                   'accepts input as a file or stdin and can write out to '
                   'a file or stdout.')
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument('-v', '--version', action='store_true',
                        help='show the version number and exit')
    parser.add_argument('infile', nargs='?', type=argparse.FileType(),
                        help='a textile file to be converted')
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'),
                        help='write the output of infile to outfile')
    options = parser.parse_args()

    if options.version:
        print(textile.VERSION)
        sys.exit()

    infile = options.infile or sys.stdin
    outfile = options.outfile or sys.stdout
    with infile:
        output = textile.textile(''.join(infile.readlines()))
    with outfile:
        outfile.write(output)


if __name__ == '__main__':  # pragma: no cover
    main()
