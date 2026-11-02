import re
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders


def test_front_page_row_gutter_stays_inside_the_mobile_page_inset():
    """The row's -15px gutter is wider than the 12px page inset and scrolls the page sideways."""
    scss_path = finders.find('pretixpresale/scss/_event.scss')
    assert scss_path is not None
    scss = Path(scss_path).read_text(encoding='utf-8')

    mobile_rules = re.search(r'^@media \(max-width: 768px\) \{\n(.*?)^\}', scss, re.M | re.S)
    assert mobile_rules is not None
    assert re.search(r'\.front-page > \.row \{\s*margin-left: 0;\s*margin-right: 0;', mobile_rules[1])
    # The column padding has to go with the gutter, or the text moves inwards.
    assert re.search(r'> \[class\*="col-"\] \{\s*padding-left: 0;\s*padding-right: 0;', mobile_rules[1])


def test_speaker_cards_fill_the_grid_on_mobile():
    """Both list variants cap the card width on larger screens, so both need the mobile override."""
    vue_path = Path(settings.BASE_DIR) / 'webapp/schedule/src/components/SpeakersList.vue'
    vue = vue_path.read_text(encoding='utf-8')

    mobile_rules = re.search(r'^@media \(max-width: 600px\)\n((?:[ \t]+.*\n)+)', vue, re.M)
    assert mobile_rules is not None
    assert (
        '\t\t.speakers-details .featured-speaker-stack,\n'
        '\t\t&:not(.is-embedded) .speakers-details .featured-speaker-stack\n'
        '\t\t\tmax-width: 100%\n'
    ) in mobile_rules[1]
