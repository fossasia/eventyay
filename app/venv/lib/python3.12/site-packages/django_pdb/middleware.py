from __future__ import print_function

import inspect
import os
import pdb
import sys

from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed

from django_pdb.utils import get_ipdb, has_ipdb


try:
    # MiddlewareMixin offers compatibility with both MIDDLEWARE and the old MIDDLEWARE_CLASSES.
    from django.utils.deprecation import MiddlewareMixin
    parent = MiddlewareMixin
except ImportError:
    parent = object


class PdbMiddleware(parent):
    """
    Middleware to break into pdb at the start of views.

    If `always_break` is set, due to `runserver --pdb` this will break
    into pdb at the start of every view.

    Otherwise it will break into pdb at the start of the view if
    a 'pdb' GET parameter is set on the request url.
    """

    always_break = False

    def __init__(self, get_response=None, debug_only=True):
        """
        If debug_only is True, this middleware removes itself
        unless settings.DEBUG is also True. Otherwise, this middleware
        is always active.
        """
        self.get_response = get_response
        if debug_only and not settings.DEBUG:
            raise MiddlewareNotUsed()

    def get_type_pdb(self, request):
        type_pdb = None
        if self.always_break:
            type_pdb = self.always_break
        elif request.GET.get('pdb', None) is not None:
            type_pdb = 'pdb'
        elif request.GET.get('ipdb', None) is not None:
            type_pdb = 'ipdb'
        return type_pdb

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        If running with '--pdb', set a breakpoint at the start
        of each of each view before it gets called.
        """
        # Skip out unless using `runserver --pdb`,
        # or `pdb` is in the command line parameters
        type_pdb = self.get_type_pdb(request)
        if not type_pdb:
            return

        filename = inspect.getsourcefile(view_func)
        basename = os.path.basename(filename)
        dirname = os.path.basename(os.path.dirname(filename))
        lines, lineno = inspect.getsourcelines(view_func)
        temporary = True
        cond = None
        funcname = view_func.__name__

        print()
        print('{} {}'.format(request.method, request.get_full_path()))
        print('function "{}" in {}/{}:{}'.format(funcname,
              dirname, basename, lineno))
        print('args: {}'.format(view_args))
        print('kwargs: {}'.format(view_kwargs))
        print()

        if type_pdb == 'ipdb' and has_ipdb():
            p = get_ipdb()
        else:
            if not type_pdb == 'pdb':
                print('You do not install ipdb or ipython module')
            p = pdb.Pdb()
        p.reset()
        p.set_break(filename, lineno + 1, temporary, cond, funcname)
        sys.settrace(p.trace_dispatch)
