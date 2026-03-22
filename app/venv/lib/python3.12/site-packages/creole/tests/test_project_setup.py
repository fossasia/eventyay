"""
    :copyleft: 2020 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""
from pathlib import Path

from poetry_publish.tests.test_project_setup import test_poetry_check as assert_poetry_check
from poetry_publish.tests.test_project_setup import test_version as assert_version

from creole import __version__
from creole.setup_utils import update_rst_readme
from creole.tests.constants import CREOLE_PACKAGE_ROOT


def test_version():
    """
    Check if current version exists in README
    Check if current version is in pyproject.toml
    """
    assert_version(package_root=CREOLE_PACKAGE_ROOT, version=__version__)


def test_update_rst_readme(capsys):
    rest_readme_path = update_rst_readme(
        package_root=CREOLE_PACKAGE_ROOT, filename='README.creole'
    )
    captured = capsys.readouterr()
    assert captured.out == 'Generate README.rst from README.creole...nothing changed, ok.\n'
    assert captured.err == ''
    assert isinstance(rest_readme_path, Path)
    assert str(rest_readme_path).endswith('/README.rst')


def test_poetry_check():
    """
    Test 'poetry check' output.
    """
    assert_poetry_check(package_root=CREOLE_PACKAGE_ROOT)
