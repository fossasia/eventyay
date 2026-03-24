#!/usr/bin/env python3
"""Check .po files for format placeholder mismatches between msgid and msgstr.

This script scans all .po files under the given base directory (default: the
eventyay/locale directory relative to the script) and reports entries where
msgid contains named format placeholders (Python %-format or brace-format) but
msgstr is missing one or more of them.

Usage:
    python tools/check_po_placeholders.py [locale_base_dir]

Exit code:
    0  No mismatches found.
    1  One or more placeholder mismatches found (build-breaking).
"""

import os
import re
import sys

try:
    import polib
except ImportError:
    print("Error: polib is not installed. Run: pip install polib", file=sys.stderr)
    sys.exit(2)

# Python %-format named placeholders, e.g. %(name)s, %(count)d
PERCENT_RE = re.compile(
    r'%\(([^)]+)\)[#0\- +]*[0-9]*(?:\.[0-9]+)?[diouxXeEfFgGcrs]'
)
# Python brace-format named placeholders, e.g. {key}, {value}
BRACE_RE = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')


def extract_placeholders(text: str) -> set[str]:
    """Return the set of named placeholder identifiers found in *text*."""
    names: set[str] = set()
    names.update(m.group(1) for m in PERCENT_RE.finditer(text or ''))
    names.update(m.group(1) for m in BRACE_RE.finditer(text or ''))
    return names


def check_entry(entry: 'polib.POEntry') -> list[tuple[int, str]]:
    """Return a list of (form_index, description) for each broken plural/singular form."""
    errors = []
    id_ph = extract_placeholders(entry.msgid)
    if not id_ph:
        return errors

    if entry.msgstr_plural:
        for idx, msgstr in entry.msgstr_plural.items():
            if not msgstr:
                continue
            str_ph = extract_placeholders(msgstr)
            missing = id_ph - str_ph
            if missing:
                errors.append((idx, f"missing {sorted(missing)} in msgstr[{idx}]"))
    else:
        if not entry.msgstr:
            return errors
        str_ph = extract_placeholders(entry.msgstr)
        missing = id_ph - str_ph
        if missing:
            errors.append((0, f"missing {sorted(missing)} in msgstr"))

    return errors


def check_po_file(path: str) -> list[tuple[int, str, str, list[tuple[int, str]]]]:
    """Return a list of (linenum, msgid, msgstr, errors) for each broken entry."""
    try:
        po = polib.pofile(path)
    except OSError as e:
        print(f"Warning: could not read {path}: {e}", file=sys.stderr)
        return []

    results = []
    for entry in po:
        errors = check_entry(entry)
        if errors:
            msgstr_preview = entry.msgstr or str(entry.msgstr_plural)
            results.append((entry.linenum, entry.msgid, msgstr_preview, errors))
    return results


def main() -> int:
    if len(sys.argv) > 1:
        base = sys.argv[1]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(script_dir, '..', 'eventyay', 'locale')

    base = os.path.normpath(base)
    if not os.path.isdir(base):
        print(f"Error: directory not found: {base}", file=sys.stderr)
        return 2

    total_errors = 0
    for root, _dirs, files in os.walk(base):
        for filename in files:
            if not filename.endswith('.po'):
                continue
            filepath = os.path.join(root, filename)
            issues = check_po_file(filepath)
            if not issues:
                continue
            print(f"File: {filepath}")
            for linenum, msgid, msgstr, errors in issues:
                print(f"  line {linenum}:")
                print(f"    msgid:  {msgid[:120].replace(chr(10), '\\n')}")
                print(f"    msgstr: {msgstr[:120].replace(chr(10), '\\n')}")
                for _idx, description in errors:
                    print(f"    error:  {description}")
            print()
            total_errors += len(issues)

    if total_errors:
        print(
            f"Found {total_errors} entry/entries with placeholder mismatches. "
            "Fix the .po files before building.",
            file=sys.stderr,
        )
        return 1

    print("All .po files look good — no placeholder mismatches found.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
