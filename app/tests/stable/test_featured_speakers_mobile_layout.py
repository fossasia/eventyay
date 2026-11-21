from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cssutils import CSSParser
from cssutils.css import CSSMediaRule

import eventyay
from eventyay.presale.style import compile_scss


EVENTYAY = Path(eventyay.__file__).parent


def indented_block(source, selector):
    lines = source.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == selector)
    indent = len(lines[start]) - len(lines[start].lstrip())
    block = []
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        block.append(line)
    return '\n'.join(block)


def test_featured_speakers_mobile_layout_stays_within_viewport():
    """Keep embedded speaker cards constrained on narrow screens."""
    source = (
        EVENTYAY / 'webapp' / 'schedule' / 'src' / 'components' / 'SpeakersList.vue'
    ).read_text(encoding='utf-8')

    style_source = source.split('<style lang="stylus">', 1)[1]
    mobile = indented_block(style_source, '@media (max-width: 600px)')
    mobile_list = indented_block(mobile, '.c-speakers-list')
    embedded = indented_block(mobile_list, '&.is-embedded')
    mobile_grid = indented_block(mobile_list, '.speakers-details .featured-speakers-grid')
    mobile_stack = indented_block(mobile_list, '.speakers-details .featured-speaker-stack')
    mobile_column = indented_block(mobile_list, '.speakers-details .featured-speaker-column')
    mobile_card = indented_block(mobile_list, '.speakers-details .featured-speaker-card')
    standalone_stack = indented_block(
        mobile_list, '&:not(.is-embedded) .speakers-details .featured-speaker-stack'
    )

    details = indented_block(style_source, '.speakers-details')
    desktop_grid = indented_block(details, '.featured-speakers-grid')
    desktop_card = indented_block(details, '.featured-speaker-card')

    assert 'justify-content: flex-start' in desktop_grid
    assert 'justify-content: center' in mobile_grid
    assert 'padding: 0 0.1rem' in embedded
    assert 'box-sizing: border-box' in mobile_list
    assert 'featured-speakers-grid' not in embedded
    assert 'min-width: 0' in mobile_grid
    assert 'min-width: 0' in mobile_stack
    assert 'min-width: 0' in mobile_column
    assert 'max-width: 100%' in standalone_stack
    assert 'max-width: 100vw' not in embedded
    assert 'overflow-x: hidden' not in embedded
    assert 'width: 100%' in desktop_card
    assert 'box-sizing: border-box' in desktop_card
    assert 'max-width: 100%' in mobile_card


def test_mobile_ticket_status_row_rule_is_scoped_to_front_page():
    """Ensure the compiled mobile override targets the front-page status row."""
    with patch('eventyay.presale.style.settings.STATIC_ROOT', EVENTYAY / 'static'):
        css, _ = compile_scss(SimpleNamespace(settings={}), fonts=False)
    stylesheet = CSSParser(raiseExceptions=False, validate=False).parseString(css)

    mobile_rule = next(
        rule
        for rule in stylesheet.cssRules
        if isinstance(rule, CSSMediaRule)
        and any(
            getattr(nested, 'selectorText', '') == '.front-page .order-status-row'
            for nested in rule.cssRules
        )
    )
    row_rule = next(
        nested
        for nested in mobile_rule.cssRules
        if getattr(nested, 'selectorText', '') == '.front-page .order-status-row'
    )

    assert row_rule.style.getPropertyValue('margin-left') == '0'
    assert row_rule.style.getPropertyValue('margin-right') == '0'
