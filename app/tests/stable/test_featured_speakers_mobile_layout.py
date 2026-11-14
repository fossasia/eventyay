from pathlib import Path

import eventyay


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


def css_block(source, selector):
    start = source.index(selector)
    opening = source.index('{', start)
    depth = 1
    for index in range(opening + 1, len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f'Unclosed CSS block for {selector}')


def test_featured_speakers_mobile_layout_stays_within_viewport():
    """Keep embedded speaker cards constrained on narrow screens."""
    source = (
        EVENTYAY / 'webapp' / 'schedule' / 'src' / 'components' / 'SpeakersList.vue'
    ).read_text(encoding='utf-8')

    style_source = source.split('<style lang="stylus">', 1)[1]
    mobile = indented_block(style_source, '@media (max-width: 600px)')
    embedded = indented_block(indented_block(mobile, '.c-speakers-list'), '&.is-embedded')
    mobile_grid = indented_block(embedded, '.featured-speakers-grid')
    mobile_card = indented_block(embedded, '.featured-speaker-card')

    details = indented_block(style_source, '.speakers-details')
    desktop_grid = indented_block(details, '.featured-speakers-grid')
    desktop_card = indented_block(details, '.featured-speaker-card')

    assert 'justify-content: flex-start' in desktop_grid
    assert 'justify-content: center' in mobile_grid
    assert 'padding: 0 1rem' in embedded
    assert 'width: 100%' in embedded
    assert 'max-width: 100%' in embedded
    assert 'max-width: 100vw' not in embedded
    assert 'overflow-x: hidden' not in embedded
    assert 'width: 100%' in desktop_card
    assert 'box-sizing: border-box' in desktop_card
    assert 'max-width: 100%' in mobile_card


def test_mobile_ticket_status_row_removes_horizontal_overflow():
    """Keep the mobile ticket status row inside the presale container."""
    source = (
        EVENTYAY / 'static' / 'pretixpresale' / 'scss' / '_event.scss'
    ).read_text(encoding='utf-8')

    mobile_rules = css_block(source, '@media (max-width: $screen-sm-max)')
    row_rules = css_block(mobile_rules, '.order-status-row')

    assert 'margin-left: 0;' in row_rules
    assert 'margin-right: 0;' in row_rules
