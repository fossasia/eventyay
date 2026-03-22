"""
    unittest subprocess helper
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2015-2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import os
import shutil
import subprocess
import sys
from pathlib import Path


class SubprocessMixin:

    def subprocess(self, popen_args):
        assert isinstance(popen_args, (tuple, list))

        print("Call:", popen_args)

        # Expand PATH
        bin_path = str(Path(sys.executable).parent)
        if bin_path not in os.environ["PATH"]:
            # .../venv/bin will be not in PATH in tests, just add it
            # so that installed [tool.poetry.scripts] will be found
            os.environ["PATH"] += os.pathsep + bin_path

        # Check if executeable will be found
        prog = popen_args[0]
        cmd = shutil.which(prog)
        assert cmd is not None, f'{prog!r} not found in PATH: {os.environ.get("PATH")!r}!'

        try:
            process = subprocess.Popen(
                popen_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )
        except Exception as err:
            self.fail(f"Error subprocess call with {popen_args!r}: {err}")

        stdout, stderr = process.communicate()
        retcode = process.poll()

        print(f"return code: {retcode!r}")
        print(f"stdout: {stdout!r}")
        print(f"stderr: {stderr!r}")

        stdout = stdout.strip()
        print("=" * 100)
        print("stdout:")
        print("-" * 100)
        print(stdout)
        print("-" * 100)
        return popen_args, retcode, stdout

    def assertSubprocess(self, popen_args, retcode, stdout):
        popen_args2, retcode2, stdout2 = self.subprocess(popen_args)
        stdout = stdout.strip()
        try:
            self.assertEqual(stdout, stdout2, "stdout wrong:")
            self.assertEqual(retcode, retcode2, "return code wrong:")
        except AssertionError as err:
            msg = (
                "Error: %s"
                "call via subprocess: %s\n"
                "return code........: %r\n"
                " ---------- [stdout] ---------- \n"
                "%s\n"
                "-------------------------------"
            ) % (
                err,
                repr(popen_args2), retcode2,
                stdout2,
            )
            self.fail(msg)
