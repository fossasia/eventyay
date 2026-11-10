from pathlib import Path

import eventyay


EVENTYAY = Path(eventyay.__file__).parent


def test_featured_speakers_mobile_layout_stays_within_viewport():
    """Keep embedded speaker cards constrained on narrow screens."""
    source = (
        EVENTYAY / 'webapp' / 'schedule' / 'src' / 'components' / 'SpeakersList.vue'
    ).read_text(encoding='utf-8')

    mobile_rules = source[source.index('@media (max-width: 600px)'):]

    assert '&.is-embedded' in mobile_rules
    assert 'padding: 0 16px' in mobile_rules
    assert 'width: 100%' in mobile_rules
    assert 'max-width: 100vw' in mobile_rules
    assert 'overflow-x: hidden !important' in mobile_rules
    assert '.featured-speaker-card' in mobile_rules
    assert 'max-width: 100%' in mobile_rules


def test_mobile_ticket_status_row_removes_horizontal_overflow():
    """Keep the mobile ticket status row inside the presale container."""
    source = (
        EVENTYAY / 'static' / 'pretixpresale' / 'scss' / '_event.scss'
    ).read_text(encoding='utf-8')

    mobile_rules = source[source.index('@media (max-width: $screen-sm-max)'):]

    assert '.order-status-row' in mobile_rules
    assert 'margin-left: 0;' in mobile_rules
    assert 'margin-right: 0;' in mobile_rules
