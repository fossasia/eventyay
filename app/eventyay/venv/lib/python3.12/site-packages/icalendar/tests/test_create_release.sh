#!/bin/sh
#
# Create a release file and test it.
#

set -e
cd "`dirname \"$0\"`"
cd "../../.."

rm -rf dist
pip3 install build
python3 -m build
archive=`echo dist/icalendar-*.tar.gz`

if ! [ -f "$archive" ]; then
  echo "ERROR: Cannot find distribution archive '$archive'."
  exit 1
fi

if tar -tf "$archive" | grep -q 'fuzzing/'; then
  echo "ERROR: Fuzzing files are included in the release."
  echo "       See https://github.com/collective/icalendar/pull/569"
  exit 1
fi

if ! tar -tf "$archive" | grep -q '/docs/'; then
  echo "ERROR: The documentation is not included in the release, but should be."
  echo "       See https://github.com/collective/icalendar/issues/712"
  exit 1
fi

echo "Checks passed."
