##
# Copyright (c) 2013 Sprymix Inc.
# All rights reserved.
#
# See LICENSE for details.
##


import argparse
import csscompressor


def _get_args():
    parser = argparse.ArgumentParser(
                description='CSS Compressor {}'.format(csscompressor.__version__))

    parser.add_argument('input', nargs='+', type=str,
                        help='File(s) to compress')
    parser.add_argument('--line-break', type=int, metavar='<column>',
                        help='Insert a line break after the specified column number')
    parser.add_argument('-o', '--output', type=str, metavar='<file>',
                        help='Place the output into <file>. Defaults to stdout')

    args = parser.parse_args()
    return args


def main():
    args = _get_args()

    buffer = []
    for name in args.input:
        with open(name, 'rt') as f:
            buffer.append(f.read())
    buffer = '\n\n'.join(buffer)

    line_break = 0
    if args.line_break is not None:
        line_break = args.line_break

    output = csscompressor.compress(buffer, max_linelen=line_break)

    if args.output:
        with open(args.output, 'wt') as f:
            f.write(output)
            f.write('\n')
    else:
        print(output)


main()
