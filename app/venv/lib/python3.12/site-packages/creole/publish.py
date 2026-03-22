from pathlib import Path

from poetry_publish.publish import poetry_publish
from poetry_publish.utils.subprocess_utils import verbose_check_call

import creole
from creole.setup_utils import assert_rst_readme


def publish():
    """
        Publish python-creole to PyPi
        Call this via:
            $ poetry run publish
    """
    package_root = Path(creole.__file__).parent.parent

    # don't publish if README is not up-to-date:
    assert_rst_readme(package_root=package_root, filename='README.creole')

    # don't publish if code style wrong:
    verbose_check_call('make', 'fix-code-style')

    poetry_publish(
        package_root=package_root,
        version=creole.__version__,
        creole_readme=True  # don't publish if README.rst is not up-to-date
    )
