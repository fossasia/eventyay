"""Gzip /static/ responses from the development static-file handler.

The handler serves files before Django middleware runs, so GZipMiddleware
never sees them.
"""

_installed = False


def install_static_gzip():
    global _installed
    if _installed:
        return
    from django.contrib.staticfiles.handlers import StaticFilesHandlerMixin

    from eventyay.common.gzip import gzip_if_accepted

    original_serve = StaticFilesHandlerMixin.serve

    def serve(self, request):
        return gzip_if_accepted(request, original_serve(self, request))

    StaticFilesHandlerMixin.serve = serve
    _installed = True
