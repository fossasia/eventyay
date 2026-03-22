"""
    unittest for CLI
    ~~~~~~~~~~~~~~~~

    :copyleft: 2013-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import sys
import tempfile
import unittest

from creole import VERSION_STRING, cmdline
from creole.tests.utils.base_unittest import BaseCreoleTest
from creole.tests.utils.unittest_subprocess import SubprocessMixin


CMDS = ("creole2html", "html2creole", "html2rest", "html2textile")


class CliTestMixins:
    def test_creole2html(self):
        self._test_convert(
            source_content=b"= test creole2html =",
            dest_content="<h1>test creole2html</h1>",
            cli_str="creole2html",
        )

    def test_html2creole(self):
        self._test_convert(
            source_content=b"<h1>test html2creole</h1>",
            dest_content="= test html2creole",
            cli_str="html2creole",
        )

    def test_html2rest(self):
        self._test_convert(
            source_content=b"<h1>test html2rest</h1>",
            dest_content=(
                "==============\n"
                "test html2rest\n"
                "=============="
            ),
            cli_str="html2rest",
        )

    def test_html2textile(self):
        self._test_convert(
            source_content=b"<h1>test html2textile</h1>",
            dest_content="h1. test html2textile",
            cli_str="html2textile",
        )


class CreoleCLITests(BaseCreoleTest, SubprocessMixin, CliTestMixins):
    def _test_convert(self, source_content, dest_content, cli_str, verbose=True):
        assert isinstance(source_content, bytes), type(source_content)

        source_file = tempfile.NamedTemporaryFile()
        sourcefilepath = source_file.name
        source_file.write(source_content)
        source_file.seek(0)

        dest_file = tempfile.NamedTemporaryFile()
        destfilepath = dest_file.name

        stdout = (
            "Convert '%(src)s' to '%(dst)s' with %(prog)s (codec: utf-8)\n"
            "done. '%(dst)s' created."
        ) % {
            "prog": cli_str,
            "src": sourcefilepath,
            "dst": destfilepath,
        }

        self.assertSubprocess(
            popen_args=[cli_str, sourcefilepath, destfilepath],
            retcode=0, stdout=stdout,
        )

        dest_file.seek(0)
        result_content = dest_file.read()

        result_content = result_content.decode("utf-8")
        self.assertEqual(result_content, dest_content)

    def test_version(self):
        for cmd in CMDS:
            version_info = f"{cmd} from python-creole v{VERSION_STRING}"
            self.assertSubprocess(
                popen_args=[cmd, "--version"],
                retcode=0,
                stdout=version_info,
            )


class CreoleCLITestsDirect(BaseCreoleTest, CliTestMixins):

    def setUp(self):
        super().setUp()
        self._old_sys_argv = sys.argv[:]

    def tearDown(self):
        sys.argv = self._old_sys_argv

    def _test_convert(self, source_content, dest_content, cli_str, verbose=True):
        assert isinstance(source_content, bytes), type(source_content)

        source_file = tempfile.NamedTemporaryFile()
        sourcefilepath = source_file.name
        source_file.write(source_content)
        source_file.seek(0)

        dest_file = tempfile.NamedTemporaryFile()
        destfilepath = dest_file.name

        sys.argv = [cli_str, sourcefilepath, destfilepath]
        cli = getattr(cmdline, f"cli_{cli_str}")
        cli()

        dest_file.seek(0)
        result_content = dest_file.read()

        result_content = result_content.decode("utf-8")
        self.assertEqual(result_content, dest_content)


if __name__ == '__main__':
    unittest.main()
