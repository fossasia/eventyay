"""Tests for test_durations_drift.py. Run with:

uvx --with pytest-split python -m unittest discover -s .github/scripts -p '*_test.py'
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_durations_drift import load_durations, main, should_refresh


# Collection order d, a, b, c. The committed file times every test at 1s, so two
# shards split as [d, a] and [b, c]: 50s and 20s with the fresh durations. The
# refreshed file splits them as [d] and [a, b, c]: 40s and 30s. Gain: 10s.
NODEIDS = ['t.py::d', 't.py::a', 't.py::b', 't.py::c']
COMMITTED = {nodeid: 1.0 for nodeid in NODEIDS}
REFRESHED = {'t.py::d': 40.0, 't.py::a': 10.0, 't.py::b': 10.0, 't.py::c': 10.0}


class DriftTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write(self, name, content):
        path = self.dir / name
        path.write_text(content if isinstance(content, str) else json.dumps(content))
        return str(path)

    def run_main(self, *extra, old=COMMITTED, new=REFRESHED):
        argv = [
            self.write('old.json', old),
            self.write('new.json', new),
            self.write('nodeids.txt', '\n'.join(NODEIDS) + '\n\n4 tests collected in 0.01s\n'),
            '--splits',
            '2',
            *extra,
        ]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            refresh = main(argv)
        return refresh, out.getvalue()

    def test_gain_equal_to_threshold_refreshes(self):
        refresh, out = self.run_main('--min-gain', '10')
        self.assertTrue(refresh)
        self.assertIn('refresh=true', out)

    def test_gain_below_threshold_does_not_refresh(self):
        refresh, out = self.run_main('--min-gain', '10.1')
        self.assertFalse(refresh)
        self.assertIn('refresh=false', out)

    def test_force_refreshes_without_gain(self):
        refresh, out = self.run_main('--min-gain', '1000', '--force')
        self.assertTrue(refresh)
        self.assertIn('refresh forced', out)

    def test_identical_files_do_not_refresh(self):
        refresh, _ = self.run_main('--min-gain', '0.1', old=REFRESHED)
        self.assertFalse(refresh)

    def test_should_refresh_boundaries(self):
        self.assertFalse(should_refresh([30.0], [15.1], 15))
        self.assertTrue(should_refresh([30.0], [15.0], 15))
        self.assertTrue(should_refresh([30.0], [30.0], 15, force=True))

    def test_rejects_non_object_file(self):
        with self.assertRaises(SystemExit):
            load_durations(self.write('list.json', []))

    def test_rejects_invalid_durations(self):
        for bad in ('"1"', 'true', '-1', 'NaN', 'Infinity'):
            with self.subTest(value=bad), self.assertRaises(SystemExit):
                load_durations(self.write('bad.json', f'{{"t.py::a": {bad}}}'))


if __name__ == '__main__':
    unittest.main()
