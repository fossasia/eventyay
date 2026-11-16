from django import template

from eventyay.common.redirects import external_link_origin


register = template.Library()
register.simple_tag(external_link_origin)
