"""
    unittest
    ~~~~~~~~

    :copyleft: 2015-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import sys
import unittest

from creole.tests.utils.unittest_subprocess import SubprocessMixin


class TestSubprocessMixin(unittest.TestCase, SubprocessMixin):

    def test_subprocess(self):
        popen_args, retcode, stdout = self.subprocess(
            popen_args=[sys.executable, "-c", "import sys;sys.stdout.write('to stdout')"],
        )
        self.assertEqual(stdout, "to stdout")
        self.assertEqual(retcode, 0)

    def test_assertSubprocess(self):
        code = (
            "import sys;"
            "sys.stdout.write('to stdout 1\\n');"
            "sys.stdout.flush();"
            "sys.stderr.write('to stderr 1\\n');"
            "sys.stderr.flush();"
            "sys.stdout.write('to stdout 2\\n');"
            "sys.stdout.flush();"
            "sys.stderr.write('to stderr 2\\n');"
            "sys.stderr.flush();"
        )
        self.assertSubprocess(
            popen_args=(sys.executable, "-c", code),
            retcode=0,
            stdout=(
                "to stdout 1\n"
                "to stderr 1\n"
                "to stdout 2\n"
                "to stderr 2\n"
            ),
        )
