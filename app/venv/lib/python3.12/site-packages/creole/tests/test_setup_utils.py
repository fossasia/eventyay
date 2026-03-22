import tempfile
from pathlib import Path

import pytest

from creole.setup_utils import _generate_rst_readme, update_rst_readme
from creole.tests.constants import CREOLE_PACKAGE_ROOT


def test_update_rst_readme(capsys):
    rest_readme_path = update_rst_readme(
        package_root=CREOLE_PACKAGE_ROOT, filename='README.creole'
    )
    captured = capsys.readouterr()
    assert captured.out == 'Generate README.rst from README.creole...nothing changed, ok.\n'
    assert captured.err == ''
    assert isinstance(rest_readme_path, Path)
    assert str(rest_readme_path).endswith('/README.rst')


def test_non_valid_readme(capsys):
    with tempfile.NamedTemporaryFile() as fp:
        path = Path(fp.name)
        with path.open('w') as f:
            f.write('= headline\n')
            f.write('\n')
            f.write('----\n')  # << error ;)

        with pytest.raises(SystemExit):
            _generate_rst_readme(creole_readme_path=path)

        captured = capsys.readouterr()
        assert captured.out == ''
        assert captured.err == (
            '<string>:5: (ERROR/3) Document or section may not begin with a transition.\n'
        )
