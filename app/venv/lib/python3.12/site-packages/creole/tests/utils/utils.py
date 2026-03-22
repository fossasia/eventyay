"""
    unitest generic utils
    ~~~~~~~~~~~~~~~~~~~~~

    Generic utils useable for a markup test.

    :copyleft: 2008-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from creole.shared.diff_utils import unified_diff


class MarkupTest(unittest.TestCase):
    """
    Special error class: Try to display markup errors in a better way.
    """

    # error output format:
    # =1 -> via repr()
    # =2 -> raw
    VERBOSE = 1
    #VERBOSE = 2

    def _format_output(self, txt):
        txt = txt.split("\\n")
        if self.VERBOSE == 1:
            txt = "".join(f'{i}\\n\n' for i in txt)
        elif self.VERBOSE == 2:
            txt = "".join(f'{i}\n' for i in txt)
        return txt

    def assertEqual(self, first, second, msg=""):
        if first == second:
            return

        try:
            diff = unified_diff(first, second)
        except AttributeError:
            raise self.failureException(f"{first!r} is not {second!r}")

        print("*" * 100)
        print("---[Output:]-----------------------------------------------------------------------------------------")
        print(first)
        print("---[not equal to:]-----------------------------------------------------------------------------------")
        print(second)
        print("---[diff:]-------------------------------------------------------------------------------------------")
        print(diff)
        print("*" * 100)

        assert first == second, f"{first!r} is not {second!r}"

    def _prepare_text(self, txt):
        """
        prepare the multiline, indentation text.
        """
        # Remove any common leading whitespace from every line
        txt = textwrap.dedent(txt)

        # Strip spaces and every line end and remove the last line ending:
        txt = "\n".join(line.rstrip(" ") for line in txt.splitlines())

        # strip *one* newline at the beginning...
        if txt.startswith("\n"):
            txt = txt[1:]

        return txt


class IsolatedFilesystem:
    """
    Context manager, e.g.:
    with IsolatedFilesystem(prefix="temp_dir_prefix"):
        print("I'm in the temp path here: %s" % Path().cwd())
    """

    def __init__(self, prefix=None):
        super().__init__()

        self.prefix = prefix

    def __enter__(self):
        print(f"Use prefix: {self.prefix!r}")

        self.cwd = Path().cwd()
        self.temp_path = tempfile.mkdtemp(prefix=self.prefix)
        os.chdir(self.temp_path)

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(str(self.cwd))  # str() needed for older python <=3.5
        try:
            shutil.rmtree(self.temp_path)
        except OSError:
            pass
