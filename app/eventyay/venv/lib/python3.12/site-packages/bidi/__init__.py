#!/usr/bin/env python
# This file is part of python-bidi
#
# python-bidi is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Copyright (C) 2008-2010 Yaacov Zamir <kzamir_a_walla.co.il>,
# Copyright (C) 2010-2024 Meir kriheli <mkriheli@gmail.com>.
#

from .wrapper import get_base_level, get_display

__all__ = ["get_base_level", "get_display"]

VERSION_TUPLE = (0, 6, 0)
VERSION = ".".join(str(x) for x in VERSION_TUPLE)


def main():
    """Will be used to create the console script"""

    import argparse
    import sys

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-e",
        "--encoding",
        dest="encoding",
        default="utf-8",
        type=str,
        help="Text encoding (default: utf-8)",
    )

    parser.add_argument(
        "-u",
        "--upper-is-rtl",
        dest="upper_is_rtl",
        default=False,
        action="store_true",
        help="Treat upper case chars as strong 'R' "
        "for debugging (default: False), Ignored in Rust algo",
    )

    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        default=False,
        action="store_true",
        help="Output to stderr steps taken with the algorithm",
    )

    parser.add_argument(
        "-b",
        "--base-dir",
        dest="base_dir",
        choices=["L", "R"],
        default=None,
        type=str,
        help="Override base direction [L|R]",
    )

    parser.add_argument(
        "-r",
        "--rust",
        dest="use_rust",
        action="store_true",
        help="Use the Rust unicode-bidi implemention instead of the Python one",
    )

    parser.add_argument(
        "-v", "--version", action="version", version=f"pybidi {VERSION}"
    )

    options, rest = parser.parse_known_args()

    lines = rest or sys.stdin

    params = {
        "encoding": options.encoding,
        "base_dir": options.base_dir,
        "debug": options.debug,
    }

    if options.use_rust:
        display_func = get_display
    else:
        from .algorithm import get_display as get_display_python

        display_func = get_display_python
        params["upper_is_rtl"] = options.upper_is_rtl

    for line in lines:
        display = display_func(line, **params)
        # adjust the encoding as unicode, to match the output encoding
        if not isinstance(display, str):
            display = bytes(display).decode(options.encoding)

        print(display, end="")


if __name__ == "__main__":
    main()
