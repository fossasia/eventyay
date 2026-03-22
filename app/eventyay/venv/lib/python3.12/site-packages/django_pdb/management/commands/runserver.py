from __future__ import print_function

import sys
import pdb

from django import VERSION as DJANGO_VERSION

from django_pdb.management import load_parent_command
from django_pdb.middleware import PdbMiddleware

from optparse import make_option
from django_pdb.utils import has_ipdb
from django.views import debug


RunServerCommand = load_parent_command('runserver')

extra_options = (
    ('--pdb',
     dict(action='store_true', dest='pdb', default=False,
          help='Drop into pdb shell on at the start of any view.')),
    ('--ipdb',
     dict(action='store_true', dest='ipdb', default=False,
          help='Drop into ipdb shell on at the start of any view.')),
    ('--pm',
     dict(action='store_true', dest='pm', default=False,
          help='Drop into ipdb shell if an exception is raised in a view.')),
)


class Command(RunServerCommand):
    """
    Identical to Django's standard 'runserver' management command,
    except that it also adds support for a '--pdb' option.
    """

    if DJANGO_VERSION >= (1, 8):
        # option_list is depecated since django 1.8 because optparse
        # is replaced by argsparse. Override add_arguements() to add
        # the extra pdb and ipdb options
        def add_arguments(self, parser):
            super(Command, self).add_arguments(parser)
            for name, kwargs in extra_options:
                parser.add_argument(name, **kwargs)
    else:
        option_list = RunServerCommand.option_list + tuple(
            make_option(name, **kwargs) for name, kwargs in extra_options
        )

    def handle(self, *args, **options):
        # Add pdb middleware, if --pdb is specified, or if we're in DEBUG mode
        from django.conf import settings

        pdb_option = options.pop('pdb')
        ipdb_option = options.pop('ipdb')

        pdb_middleware = 'django_pdb.middleware.PdbMiddleware'
        middleware = (settings.MIDDLEWARE
                      if hasattr(settings, 'MIDDLEWARE')
                      else settings.MIDDLEWARE_CLASSES)
        if ((pdb_option or settings.DEBUG)
            and pdb_middleware not in middleware):
            middleware += (pdb_middleware,)

        self.pm = options.pop('pm')
        if self.pm:
            debug.technical_500_response = self.reraise

        # If --pdb is specified then always break at the start of views.
        # Otherwise break only if a 'pdb' query parameter is set in the url.
        if pdb_option:
            PdbMiddleware.always_break = 'pdb'
        elif ipdb_option:
            PdbMiddleware.always_break = 'ipdb'

        super(Command, self).handle(*args, **options)

    def reraise(self, request, exc_type, exc_value, tb):
        if has_ipdb():
            import ipdb
            p = ipdb
        else:
            p = pdb
        if self.pm:
            print(
                "Exception occured: %s, %s" % (exc_type, exc_value),
                file=sys.stderr)
            p.post_mortem(tb)
        else:
            raise
