import sys

from django.conf import settings

from eventyay.helpers.i18n import is_rtl


def contextprocessor(request):
    ctx = {
        'rtl': is_rtl(getattr(request, 'LANGUAGE_CODE', 'en')),
    }
    if settings.DEBUG and 'runserver' not in sys.argv:
        ctx['debug_warning'] = True
    elif 'runserver' in sys.argv:
        ctx['development_warning'] = True

    return ctx
