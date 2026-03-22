"""
    :copyleft: 2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import unittest

from creole.tests.utils.unittest_subprocess import SubprocessMixin


class MakefileTestCase(unittest.TestCase, SubprocessMixin):

    def test_help(self):
        popen_args, retcode, stdout = self.subprocess(
            popen_args=["make"],
        )
        assert "List all commands" in stdout
        assert "tox" in stdout
        assert "pytest" in stdout
        assert retcode == 0

    def test_check_poetry(self):
        popen_args, retcode, stdout = self.subprocess(
            popen_args=["make", "check-poetry"],
        )
        assert "Found Poetry version 1." in stdout
        assert "ok" in stdout
        assert retcode == 0
