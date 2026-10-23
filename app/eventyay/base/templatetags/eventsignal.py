import importlib

from django import template
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from eventyay.base.models import Event

register = template.Library()


@register.simple_tag
def eventsignal(event: Event, signame: str, **kwargs):
    """
    Send a signal and return the concatenated return values of all responses.

    Usage::

        {% eventsignal event "path.to.signal" argument="value" ... %}
    """
    sigstr = signame.rsplit('.', 1)
    sigmod = importlib.import_module(sigstr[0])
    signal = getattr(sigmod, sigstr[1])
    _html = []
    for receiver, response in signal.send(event, **kwargs):
        if response:
            _html.append(response)
    return mark_safe(''.join(_html))


@register.simple_tag
def signal(signame: str, request, **kwargs):
    """
    Send a signal and return the concatenated return values of all responses.

    Usage::

        {% signal request "path.to.signal" argument="value" ... %}
    """
    sigstr = signame.rsplit('.', 1)
    sigmod = importlib.import_module(sigstr[0])
    signal = getattr(sigmod, sigstr[1])
    _html = []
    for receiver, response in signal.send(request, **kwargs):
        if response:
            _html.append(response)
    return mark_safe(''.join(_html))


@register.simple_tag
def sorted_signal(signame: str, request, **kwargs):
    """
    Like ``signal``, but orders the responses by their visible text.

    Plugin entries in the global sidebar are sorted by label, so menus that
    list the same entries as HTML use this to show them in the same order.

    Usage::

        {% sorted_signal "path.to.signal" request argument="value" ... %}
    """
    sigstr = signame.rsplit('.', 1)
    sigmod = importlib.import_module(sigstr[0])
    signal = getattr(sigmod, sigstr[1])
    responses = [response for receiver, response in signal.send(request, **kwargs) if response]
    responses.sort(key=lambda response: strip_tags(str(response)).strip())
    return mark_safe(''.join(responses))
