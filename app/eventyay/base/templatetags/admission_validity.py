from django import template

from eventyay.base.admission_validity import (
    format_catalog_admission_validity,
    format_issued_admission_validity,
)

register = template.Library()


@register.simple_tag
def product_admission_validity_text(product, event, subevent=None, variation=None):
    return format_catalog_admission_validity(product, event, subevent, variation=variation)


@register.simple_tag
def position_admission_validity_text(position, event):
    return format_issued_admission_validity(position, event)
