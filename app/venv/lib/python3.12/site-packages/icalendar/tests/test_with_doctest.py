"""This file tests the source code provided by the documentation.

See
- doctest documentation: https://docs.python.org/3/library/doctest.html
- :issue:`443`

This file should be tests, too:

    >>> print("Hello World!")
    Hello World!

"""

import doctest
import importlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__ or ".").absolute().parent
ICALENDAR_PATH = HERE / ".."

PYTHON_FILES = [
    file
    for file in ICALENDAR_PATH.glob("**/*.py")
    if "fuzzing" not in file.relative_to(ICALENDAR_PATH).parts
]

MODULE_NAMES = [
    "icalendar"
    + str(python_file)[len(str(ICALENDAR_PATH)) : -3]
    .replace("\\", "/")
    .replace("/", ".")
    for python_file in PYTHON_FILES
]


def test_this_module_is_among_them():
    assert __name__ in MODULE_NAMES


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_docstring_of_python_file(module_name, env_for_doctest):
    """This test runs doctest on the Python module."""
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name == "pytz":
            pytest.skip("pytz is not installed, skipping this module.")
        raise
    test_result = doctest.testmod(module, name=module_name, globs=env_for_doctest)
    assert test_result.failed == 0, f"{test_result.failed} errors in {module_name}"


# This collection needs to exclude .tox and other subdirectories
REPOSITORY = HERE.parent.parent.parent
DOCUMENT_PATHS = list(REPOSITORY.glob("**/*.rst"))


@pytest.mark.parametrize(
    "filename",
    [
        "README.rst",
        "index.rst",
    ],
)
def test_files_is_included(filename):
    assert any(path.name == filename for path in DOCUMENT_PATHS)


@pytest.mark.parametrize("document", DOCUMENT_PATHS)
def test_documentation_file(document, zoneinfo_only, env_for_doctest, tzp):
    """This test runs doctest on a documentation file.

    functions are also replaced to work.
    """
    try:
        import pytz  # noqa: F401
    except ImportError:
        pytest.skip("pytz not installed, skipping this file.")
    try:
        # set raise_on_error to False if you wand to see the error for debug
        test_result = doctest.testfile(
            document, module_relative=False, globs=env_for_doctest, raise_on_error=False
        )
    finally:
        tzp.use_zoneinfo()
    assert test_result.failed == 0, (
        f"{test_result.failed} errors in {Path(document).name}"
    )


def test_can_import_zoneinfo(env_for_doctest):
    """Allow importing zoneinfo for tests."""
    assert "zoneinfo" in sys.modules
