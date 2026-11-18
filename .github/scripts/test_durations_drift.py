"""Decide whether a refreshed pytest-split durations file is worth committing.

CI splits the stable suite into shards with the committed durations file. This
script estimates how long the slowest shard takes when it is split with the
committed (old) file and with the refreshed (new) file, timing both splits with
the new durations. A refresh is only worth a pull request when it makes the
slowest shard noticeably faster, or when ``--force`` is given.

Usage:
    python test_durations_drift.py OLD_JSON NEW_JSON NODEIDS_TXT \
        --splits 4 --min-gain 15 --summary summary.md [--force]

NODEIDS_TXT lists the collected test node IDs in collection order, one per line
(the output of ``pytest --collect-only -q``). Prints ``refresh=true`` or
``refresh=false`` for ``$GITHUB_OUTPUT``.
"""

import argparse
import json
import math
from pathlib import Path
from types import SimpleNamespace

from pytest_split.algorithms import Algorithms


def load_durations(path):
    """Load a durations file and check it maps test IDs to non-negative seconds."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise SystemExit(f'{path}: expected a JSON object of test durations, got {type(data).__name__}')
    for nodeid, seconds in data.items():
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise SystemExit(f'{path}: duration for {nodeid!r} is not a number')
        if not math.isfinite(seconds) or seconds < 0:
            raise SystemExit(f'{path}: duration for {nodeid!r} must be finite and non-negative')
    return data


def read_nodeids(path):
    """Read node IDs from ``pytest --collect-only -q`` output, skipping the summary lines."""
    lines = Path(path).read_text().splitlines()
    nodeids = [line for line in lines if '::' in line and not line[:1].isspace()]
    # A warnings summary can repeat node IDs after the list; keep the first occurrence.
    return list(dict.fromkeys(nodeids))


def shard_times(nodeids, split_durations, real_durations, splits):
    """Split with ``split_durations`` and time each shard with ``real_durations``."""
    items = [SimpleNamespace(nodeid=nodeid) for nodeid in nodeids]
    groups = Algorithms.duration_based_chunks.value(splits, items, split_durations)
    average = sum(real_durations.values()) / max(len(real_durations), 1)
    return [sum(real_durations.get(item.nodeid, average) for item in group.selected) for group in groups]


def should_refresh(before, after, min_gain, force=False):
    """Refresh when forced, or when the slowest shard gets at least ``min_gain`` seconds faster."""
    return force or max(before) - max(after) >= min_gain


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('old')
    parser.add_argument('new')
    parser.add_argument('nodeids')
    parser.add_argument('--splits', type=int, default=4)
    parser.add_argument(
        '--min-gain', type=float, default=15.0, help='Seconds the slowest shard must get faster to refresh.'
    )
    parser.add_argument('--force', action='store_true', help='Refresh regardless of the gain.')
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args(argv)

    old = load_durations(args.old)
    new = load_durations(args.new)
    nodeids = read_nodeids(args.nodeids)

    before = shard_times(nodeids, old, new, args.splits)
    after = shard_times(nodeids, new, new, args.splits)
    gain = max(before) - max(after)
    refresh = should_refresh(before, after, args.min_gain, args.force)

    added = len(set(new) - set(old))
    removed = len(set(old) - set(new))

    def fmt(times):
        return ' / '.join(f'{t:.0f}s' for t in times)

    summary = '\n'.join(
        [
            '| Durations file | Estimated shard times | Slowest |',
            '|---|---|---|',
            f'| Committed | {fmt(before)} | {max(before):.0f}s |',
            f'| Refreshed | {fmt(after)} | {max(after):.0f}s |',
            '',
            f'Slowest shard gets **{gain:.0f}s** faster (threshold {args.min_gain:.0f}s'
            f'{"; refresh forced" if args.force else ""}). '
            f'Tests added since the last refresh: {added}; removed: {removed}.',
            '',
            'Shard times are test durations only; each shard also spends time building its test database.',
        ]
    )
    if args.summary:
        args.summary.write_text(summary + '\n')
    print(summary)
    print(f'refresh={"true" if refresh else "false"}')
    return refresh


if __name__ == '__main__':
    main()
