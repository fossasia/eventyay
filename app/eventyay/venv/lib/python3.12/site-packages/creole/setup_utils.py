"""
    Python setup.py utilities
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Generate ReStructuredText README from README.creole.
    Usable for other python packages, too.

    More information:
        https://github.com/jedie/python-creole/wiki/Use-In-Setup

    :copyleft: 2011-2020 by the python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import codecs
import datetime
import os
import sys
import warnings
from pathlib import Path

from readme_renderer.rst import render

from creole import creole2html, html2rest
from creole.shared.diff_utils import unified_diff
from creole.shared.unknown_tags import raise_unknown_node, transparent_unknown_nodes


RAISE_ERRORS_ARGS = (
    'check', 'register', 'sdist', 'bdist', 'upload',
    '--long-description', '--restructuredtext',
)


def should_raise_errors():
    """
    Raise only errors, if one of RAISE_ERRORS_ARGS is in sys.argv
    or if no argument presents.
    """
    if len(sys.argv) == 1:
        return True

    for arg in RAISE_ERRORS_ARGS:
        if arg in sys.argv:
            return True
    return False


def get_long_description(package_root, filename='README.creole', raise_errors=None):
    """ read README file and convert it on-the-fly to ReStructuredText. """

    warnings.warn('get_long_description() will be removed in the future', DeprecationWarning)

    if raise_errors is None:
        raise_errors = should_raise_errors()

    if raise_errors:
        sys.stderr.write('Test creole2rest and raise an error, if rendering failed...\n')
        # raise a error if a unknown node found
        unknown_emit = raise_unknown_node
    else:
        # ignore unknown nodes
        unknown_emit = transparent_unknown_nodes

    filepath = os.path.join(package_root, filename)
    long_description_origin = ''
    try:
        # Read creole README
        f = codecs.open(filepath, 'r', encoding='utf-8')
        long_description_origin = f.read().strip()
        f.close()

        # convert creole into html
        long_description_html = creole2html(long_description_origin)

        # convert html to ReSt
        long_description_rest = html2rest(
            long_description_html,
            emitter_kwargs={'unknown_emit': unknown_emit}
        )
    except Exception:
        if raise_errors:
            raise
        # Don't raise the error e.g. in ./setup install process
        evalue = sys.exc_info()[1]
        long_description_rest = f'[Error: {evalue}]\n{long_description_origin}'
    else:
        if raise_errors:
            # Test created ReSt code like PyPi does it.
            from creole.rest_tools.pypi_rest2html import pypi_rest2html
            try:
                pypi_rest2html(long_description_rest)
            except SystemExit as e:
                msg = f'Error creole2rest self test failed: rest2html() exist with status code: {e.args[0]}\n'
                sys.stderr.write(msg)
                sys.exit(msg)
            except Exception as e:
                sys.exit(f'ReSt2html error: {e}')
            else:
                if 'check' in sys.argv:
                    print('Generating creole to ReSt to html, ok.')

    return long_description_rest


def _generate_rst_readme(*, creole_readme_path):
    with creole_readme_path.open('r') as f:
        creole_readme = f.read().strip()

    # convert creole into html
    html_readme = creole2html(creole_readme)

    # convert html to ReSt
    rest_readme = html2rest(
        html_readme,
        emitter_kwargs={
            'unknown_emit': raise_unknown_node  # raise a error if a unknown node found
        }
    )

    # Check if generated ReSt is valid, see also:
    # https://pypi.org/help/#description-content-type
    rendered = render(rest_readme, stream=sys.stderr)
    if rendered is None:
        sys.exit(1)

    return rest_readme


def update_rst_readme(package_root, filename='README.creole'):
    """
    Generate README.rst from README.creole
    """
    assert isinstance(package_root, Path)
    assert package_root.is_dir(), f'Directory not found: {package_root}'
    creole_readme_path = Path(package_root, filename)
    assert creole_readme_path.is_file(), f'File not found: {creole_readme_path}'

    rest_readme_path = creole_readme_path.with_suffix('.rst')
    print(
        f'Generate {rest_readme_path.name} from {creole_readme_path.name}',
        end='...', flush=True
    )

    rest_readme = _generate_rst_readme(creole_readme_path=creole_readme_path)

    # Check if content was changed
    changed = False
    with rest_readme_path.open('r') as f:
        for new_line, old_line in zip(rest_readme.splitlines(), f):
            if new_line.rstrip() != old_line.rstrip():
                changed = True
                break

    if not changed:
        # The existing README.rst is up-to-date: Don't change the timestamp
        print('nothing changed, ok.')
        return rest_readme_path

    with rest_readme_path.open('w') as f:
        f.write(rest_readme)

        # Add a note about generation with modification time from source:

        f.write('\n\n------------\n\n')

        modification_time = creole_readme_path.stat().st_mtime
        dt = datetime.datetime.fromtimestamp(modification_time)
        dt = dt.replace(microsecond=0)
        dt = dt.isoformat(sep=' ')
        f.write(f'``Note: this file is generated from {filename} {dt} with "python-creole"``')

    print('done.')
    return rest_readme_path


def assert_rst_readme(package_root, filename='README.creole'):
    """
    raise AssertionError if README.rst is not up-to-date.
    """
    creole_readme_path = Path(package_root, filename)
    rest_readme = _generate_rst_readme(creole_readme_path=creole_readme_path)
    rest_readme_path = creole_readme_path.with_suffix('.rst')
    with rest_readme_path.open('r') as f:
        content = f.read()

    assert len(content) > 0, f'Empty content in {rest_readme_path}'
    content = content.rsplit('\n', 4)[0]  # remove note about generation with modification time

    if rest_readme != content:
        diff = unified_diff(content, rest_readme, filename=rest_readme_path.name)
        raise AssertionError(f'{rest_readme_path.name} is not up-to-date:\n{diff}')


def update_creole_rst_readme():
    return update_rst_readme(
        package_root=Path(__file__).parent.parent,
        filename='README.creole'
    )


if __name__ == '__main__':
    update_creole_rst_readme()
