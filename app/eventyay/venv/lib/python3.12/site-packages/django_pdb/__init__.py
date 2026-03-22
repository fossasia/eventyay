from __future__ import print_function
from django.conf import settings
__version__ = '0.6.2'

POST_MORTEM = getattr(settings, 'POST_MORTEM', False)
DEBUG = getattr(settings, 'DEBUG', False)

if DEBUG and POST_MORTEM == True:
    from django.views import debug
    def runpdb(request, exc_type, exc_value, tb):
        import sys
        try:
            import ipdb
        except ImportError:
            import pdb as ipdb
        p = ipdb
        print('Exception occured: {}, {}'.format(exc_type, exc_value), file=sys.stderr)
        p.post_mortem(tb)
    debug.technical_500_response = runpdb

default_app_config = 'django_pdb.apps.DjangoPdbConfig'
