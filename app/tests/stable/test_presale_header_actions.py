import re
from pathlib import Path

import django_libsass
import pytest
import sass
from bs4 import BeautifulSoup
from django.contrib.staticfiles import finders
from django.template.loader import get_template

from eventyay.orga.utils.colors import calculate_contrast_ratio


ACTION = '.panel-primary>.panel-heading .pull-right a'


def event_stylesheet():
    return sass.compile(
        filename=finders.find('pretixpresale/scss/main.scss'),
        output_style='expanded',
        custom_functions=django_libsass.CUSTOM_FUNCTIONS,
    )


def custom_stylesheet():
    return Path(finders.find('pretixpresale/scss/custom.css')).read_text(encoding='utf-8')


@pytest.fixture(scope='module', params=['event stylesheet', 'custom.css'])
def css(request):
    return event_stylesheet() if request.param == 'event stylesheet' else custom_stylesheet()


def declarations(css, selector):
    found = {}
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    for selectors, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        names = {re.sub(r'\s*>\s*', '>', ' '.join(name.split())) for name in selectors.split(',')}
        if selector in names:
            for declaration in body.split(';'):
                if ':' in declaration:
                    prop, value = declaration.split(':', 1)
                    found[prop.strip()] = ' '.join(value.split())
    return found


def rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def test_header_actions_are_dark_text_on_white(css):
    rule = declarations(css, ACTION)
    assert rule['display'] == 'inline-block'
    assert rule['background-color'] == '#fff'
    assert calculate_contrast_ratio(rgb(rule['color']), rgb(rule['background-color'])) >= 4.5
    assert rule['border'] == '1px solid #737373'

    hover = declarations(css, f'{ACTION}:hover')
    assert calculate_contrast_ratio(rgb(hover['color']), rgb(hover['background-color'])) >= 4.5


def test_header_actions_have_a_focus_ring_for_light_and_dark_headers(css):
    focus = declarations(css, f'{ACTION}:focus-visible')
    assert focus['outline'] == '2px solid #0d0f10'
    assert focus['box-shadow'] == '0 0 0 4px #fff'


@pytest.mark.parametrize(
    'template_name,label',
    [
        ('pretixpresale/event/checkout_confirm.html', 'Add or remove tickets'),
        ('pretixpresale/event/checkout_confirm.html', 'Modify'),
        ('pretixpresale/event/order.html', 'Change details'),
    ],
)
def test_header_actions_match_the_stylesheet_selector(template_name, label):
    source = Path(get_template(template_name).origin.name).read_text(encoding='utf-8')
    soup = BeautifulSoup(source, 'html.parser')
    links = [a for a in soup.find_all('a') if f'"{label}"' in a.get_text()]
    assert links, f'No "{label}" link in {template_name}'
    for link in links:
        heading = link.find_parent(class_='panel-heading')
        assert link.find_parent(class_='pull-right') in heading.find_all(class_='pull-right')
        assert 'panel-primary' in heading.parent['class']
