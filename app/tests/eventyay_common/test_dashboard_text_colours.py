"""Dashboard stylesheets take their text colours from the global stylesheet (#6280)."""

import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders


DASHBOARD_STYLESHEETS = [
    'eventyay-common/css/common_dashboard.css',
    'eventyay-common/css/dashboard.css',
    'eventyay-common/css/meetup_dashboard.css',
    'pretixcontrol/css/admin-page.css',
    'pretixcontrol/css/order-overview.css',
]

# Hard-coded text colours that duplicate --color-text, --color-text-muted or --color-grey-dark.
REPLACED_TEXT_COLOURS = re.compile(
    r'(?<![-\w])color:\s*#(111827|0f172a|212529|2c3e50|343a40|333|555|666|6b7280|6c757d|767676|495057)\b',
    re.IGNORECASE,
)


@pytest.mark.parametrize('path', DASHBOARD_STYLESHEETS)
def test_dashboard_text_colours_come_from_global_variables(path):
    css = Path(finders.find(path)).read_text()
    found = sorted({f'#{value.lower()}' for value in REPLACED_TEXT_COLOURS.findall(css)})
    assert not found, f'{path} hard-codes text colours {found}; use the global --color-* variables'
