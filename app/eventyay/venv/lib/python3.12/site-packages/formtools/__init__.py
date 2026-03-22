from importlib.metadata import PackageNotFoundError, version

import django

try:
    __version__ = version("django-formtools")
except PackageNotFoundError:
    # package is not installed
    __version__ = None

if django.VERSION <= (3, 2):
    default_app_config = 'formtools.apps.FormToolsConfig'
