import importlib
from html.parser import HTMLParser

from django import template
from django.utils.safestring import mark_safe

from eventyay.base.models import Event
from eventyay.control.navigation import global_nav_label_key

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


class _VisibleTextParser(HTMLParser):
    """Collects the text of an HTML fragment that is shown on screen."""

    VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
    HIDDEN_CLASSES = {'sr-only', 'visually-hidden'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden_stack = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID_TAGS:
            if tag == 'br' and not any(self.hidden_stack):
                self.parts.append(' ')
            return
        attrs = dict(attrs)
        classes = set((attrs.get('class') or '').split())
        self.hidden_stack.append(
            'hidden' in attrs or attrs.get('aria-hidden') == 'true' or bool(classes & self.HIDDEN_CLASSES)
        )

    def handle_endtag(self, tag):
        if tag not in self.VOID_TAGS and self.hidden_stack:
            self.hidden_stack.pop()

    def handle_data(self, data):
        if not any(self.hidden_stack):
            self.parts.append(data)


def visible_text(html) -> str:
    """Return the on-screen text of ``html``, with entities decoded and hidden elements left out."""
    parser = _VisibleTextParser()
    parser.feed(str(html))
    parser.close()
    return ' '.join(''.join(parser.parts).split())


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
    responses.sort(key=lambda response: global_nav_label_key(visible_text(response)))
    return mark_safe(''.join(responses))
