#!/usr/bin/env bash
#
# This script generates a test case from a test case file that was downloaded.
#
# You will need to follow the setup instructions here:
#   https://google.github.io/oss-fuzz/advanced-topics/reproducing/#reproduce-using-local-source-checkout
#
set -e

HERE="`dirname \"$0\"`"
OSS_FUZZ_DIRECTORY="$HOME/oss-fuzz"
DOWNLOADS_DIRECTORY="$HOME/Downloads"
LOCAL_ICALENDAR_DIRECTORY="$HERE/../../../../"
PYTHON_TEST_CASE_DIRECTORY="$HERE/../calendars/"
PROJECT_NAME="icalendar"

echo "### Building Project $PROJECT_NAME"
python "$OSS_FUZZ_DIRECTORY/infra/helper.py" build_fuzzers --sanitizer undefined "$PROJECT_NAME" "$LOCAL_ICALENDAR_DIRECTORY"

# we capture the output
OUTPUT="`mktemp`"

# test case files look like this:
#   clusterfuzz-testcase-minimized-ical_fuzzer-4878676239712256
for testcase in "$DOWNLOADS_DIRECTORY/clusterfuzz-testcase-"*
do
  echo "### Reproducing $testcase"
  python "$OSS_FUZZ_DIRECTORY/infra/helper.py" reproduce "$PROJECT_NAME" ical_fuzzer "$testcase" | tee "$OUTPUT"
  if [ $PIPESTATUS -eq 0 ]
  then
    echo "### Testcase fixed! $testcase"
    continue
  fi
  echo "### Testcase reproduced! $testcase"
  TEST_FILE_CONTENT="`cat \"$OUTPUT\" | sed -n '/--- start calendar ---/,/--- end calendar ---/{/--- start calendar ---/b;/--- end calendar ---/b;p}'`"
  if [ -z "$TEST_FILE_CONTENT" ]
  then
    echo "### No test file content for $testcase"
    exit 1
  fi
  ICS_FILE="$PYTHON_TEST_CASE_DIRECTORY/`basename \fuzz_testcase_"$testcase\"`.ics"
  # decode and ignore garbage, see https://stackoverflow.com/a/15490765/1320237
  echo $TEST_FILE_CONTENT | base64 -di > /dev/null
  echo "Created $ICS_FILE"
done
