import shutil
import subprocess
from pathlib import Path

import pytest


def test_ajax_filter_node_suite():
    node = shutil.which('node')
    if node is None:
        pytest.fail('Node.js is required to run ajax-filter.test.mjs')

    test_file = Path(__file__).with_name('ajax-filter.test.mjs')
    result = subprocess.run(
        [node, '--test', str(test_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f'node --test failed:\n{result.stdout}\n{result.stderr}'
