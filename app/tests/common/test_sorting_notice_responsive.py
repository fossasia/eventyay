import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from django.template import Context, Template
from django.test import RequestFactory


BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES = [
    BASE_DIR / 'eventyay' / 'orga' / 'templates' / 'orga' / 'schedule' / 'room' / 'list.html',
    BASE_DIR / 'eventyay' / 'orga' / 'templates' / 'orga' / 'cfp' / 'track' / 'list.html',
    BASE_DIR / 'eventyay' / 'orga' / 'templates' / 'orga' / 'cfp' / 'submissiontype' / 'list.html',
]
BASE_CSS = BASE_DIR / 'eventyay' / 'static' / 'common' / 'css' / 'base.css'

REORDER_BLOCK_PATTERN = re.compile(
    r'({% if not can_reorder %}.*?{% endif %})',
    re.DOTALL,
)

INNER_FLEX_CLASSES = (
    'd-flex flex-column flex-sm-row '
    'justify-content-between align-items-sm-center flex-grow-1'
)


def test_sorting_notice_templates_contain_responsive_classes():
    """Verify list templates have responsive mobile flex classes and separate link container (#6664)."""
    for template_path in TEMPLATES:
        content = template_path.read_text(encoding='utf-8')
        assert '<div class="alert alert-info">' in content
        assert INNER_FLEX_CLASSES in content
        assert 'mt-2 mt-sm-0 ml-sm-3 nowrap mw-100' in content
        assert 'alert-link' in content
        assert 'Reset to manual order' in content


@pytest.mark.parametrize('template_path', TEMPLATES)
def test_sorting_notice_rendered_dom_structure(template_path):
    """Verify sorting alert rendered directly from each production template has correct DOM (#6664)."""
    content = template_path.read_text(encoding='utf-8')
    match = REORDER_BLOCK_PATTERN.search(content)
    assert match is not None, f"Could not find can_reorder block in {template_path}"

    tpl_source = '{% load i18n %}\n' + match.group(1)
    tpl = Template(tpl_source)

    factory = RequestFactory()
    request = factory.get('/orga/event/schedule/rooms/?sort=name')
    context = Context({'can_reorder': False, 'request': request})
    context.request = request
    rendered = tpl.render(context)
    soup = BeautifulSoup(rendered, 'html.parser')

    alert = soup.find('div', class_='alert')
    assert alert is not None
    assert 'alert-info' in alert['class']
    # Alert itself must remain row-oriented so its ::before icon does not stretch into a full-width strip
    assert 'flex-column' not in alert.get('class', [])

    wrapper = alert.find('div', class_='d-flex')
    assert wrapper is not None
    assert 'flex-column' in wrapper['class']
    assert 'flex-sm-row' in wrapper['class']
    assert 'justify-content-between' in wrapper['class']
    assert 'align-items-sm-center' in wrapper['class']
    assert 'flex-grow-1' in wrapper['class']

    children = wrapper.find_all('div', recursive=False)
    assert len(children) == 2

    # Text container
    assert 'Manual drag-and-drop reordering is disabled while custom sorting is active.' in children[0].get_text()

    # Action link container
    assert 'mt-2' in children[1]['class']
    assert 'mt-sm-0' in children[1]['class']
    assert 'ml-sm-3' in children[1]['class']
    assert 'nowrap' in children[1]['class']
    assert 'mw-100' in children[1]['class']

    link = children[1].find('a')
    assert link is not None
    assert 'alert-link' in link['class']
    assert 'Reset to manual order' in link.get_text()
    assert link['href'] == '?'


def test_stylesheet_defines_responsive_utilities_at_breakpoint():
    """Verify base.css defines responsive flex and spacing utilities at the 768px breakpoint (#6664)."""
    assert BASE_CSS.is_file(), f"Stylesheet not found at {BASE_CSS}"
    css_content = BASE_CSS.read_text(encoding='utf-8')

    # Verify media query breakpoint
    assert '@media (min-width: 768px)' in css_content

    # Verify utility definitions
    assert '.flex-sm-row' in css_content
    assert 'flex-direction: row !important;' in css_content
    assert '.align-items-sm-center' in css_content
    assert 'align-items: center !important;' in css_content
    assert '.mt-sm-0' in css_content
    assert 'margin-top: 0 !important;' in css_content
    assert '.ml-sm-3' in css_content
    assert 'margin-left: 1rem !important;' in css_content

    # Verify loaded nowrap utility
    assert '.nowrap' in css_content
    assert 'white-space: nowrap;' in css_content

    # Precedence check: .mt-sm-0 must appear after .mt-2 in the stylesheet
    # so that the desktop override (.mt-sm-0) wins over mobile margin (.mt-2)
    mt_2_pos = css_content.find('.mt-2 {')
    mt_sm_0_pos = css_content.find('.mt-sm-0 {')
    assert mt_2_pos != -1, "Expected .mt-2 to be defined in stylesheet"
    assert mt_sm_0_pos != -1, "Expected .mt-sm-0 to be defined in stylesheet"
    assert mt_sm_0_pos > mt_2_pos, ".mt-sm-0 must appear after .mt-2 for CSS cascade precedence"
