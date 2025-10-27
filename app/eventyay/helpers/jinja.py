from django.urls import reverse
from django.utils.translation import gettext as django_gettext, ngettext
from django.utils.formats import date_format
from jinja2 import Environment, pass_context
from jinja2.runtime import Context
from eventyay.helpers.templatetags.thumb import thumb


@pass_context
def url_for(context: Context, name: str, *args, query_string=None, **kwargs):
    try:
        current_app = context['request'].current_app
    except KeyError:
        current_app = None
    except AttributeError:
        try:
            current_app = context['request'].resolver_match.namespace
        except AttributeError:
            current_app = None
    base_url = reverse(name, args=args, kwargs=kwargs, current_app=current_app)
    return f"{base_url}?{query_string}" if query_string else base_url


def jinja_gettext(message, **kwargs):
    text = django_gettext(message)
    if kwargs:
        try:
            text = text % kwargs
        except Exception:
            pass
    return text


def format_date(value, format_str="SHORT_DATE_FORMAT"):
    if not value:
        return ""
    try:
        return date_format(value, format_str)
    except Exception:
        return str(value)


def environment(**options):
    env = Environment(**options, autoescape=True)

    env.globals.update({
        'url_for': url_for,
        '_': jinja_gettext,
        'gettext': jinja_gettext,
        'ngettext': ngettext,
    })

    env.filters.update({
        'thumb': thumb,
        'format_date': format_date,
    })

    return env
