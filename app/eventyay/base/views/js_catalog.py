from django.utils import timezone
from django.utils.translation.trans_real import DjangoTranslation
from django.views.decorators.cache import cache_page
from django.views.decorators.http import etag
from django.views.i18n import JavaScriptCatalog

# Yes, we want to regenerate this every time the module has been imported to
# refresh the cache at least at every code deployment
import_date = timezone.now().strftime('%Y%m%d%H%M')


# This is not a valid Django URL configuration, as the final
# configuration is done by the pretix.multidomain package.
js_info_dict = {
    'packages': ('eventyay',),
}


@etag(lambda *s, **k: import_date)
@cache_page(3600, key_prefix='js18n-%s' % import_date)
def js_catalog(request, lang):
    """
    Serve JavaScript translation catalog for the requested language.
    
    Falls back through the language chain:
    1. Try the requested language as-is (e.g., 'pt-br')
    2. Try the primary subtag (e.g., 'pt' from 'pt-br')
    3. Fall back to English
    """
    c = JavaScriptCatalog()
    
    # Try the requested language first
    try:
        c.translation = DjangoTranslation(lang, domain='djangojs')
    except:
        # Try the primary subtag
        lang_primary = lang.split('-')[0].lower()
        try:
            c.translation = DjangoTranslation(lang_primary, domain='djangojs')
        except:
            # Fall back to English
            c.translation = DjangoTranslation('en', domain='djangojs')
    
    context = c.get_context_data()
    return c.render_to_response(context)
