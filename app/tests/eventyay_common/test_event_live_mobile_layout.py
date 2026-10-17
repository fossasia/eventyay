"""Tests for the phone layout of the common event status page.

CI does not run a browser, so these tests check what the layout depends on:
the rows are stacked only by the phone rules in dashboard.css, and every class
those rules target is still on the status page.
"""

import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.test import override_settings
from django.urls import reverse


PHONE_MEDIA_QUERY = '@media (max-width: 767px)'
STACKED_ROWS = ('.progress-row', '.section-flex-row', '.mode-flex-row')
ACTION_COLUMNS = ('.card-action-col', '.mode-action-col')


def css_blocks(css):
    """Split CSS into (prelude, body) pairs, without going into nested blocks."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    blocks = []
    depth = 0
    start = 0
    prelude = ''
    for index, char in enumerate(css):
        if char == '{':
            if depth == 0:
                prelude = css[start:index].strip()
                start = index + 1
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                blocks.append((prelude, css[start:index]))
                start = index + 1
    return blocks


def dashboard_css():
    return Path(finders.find('eventyay-common/css/dashboard.css')).read_text()


def desktop_rules():
    return [(selector, body) for selector, body in css_blocks(dashboard_css()) if not selector.startswith('@')]


def phone_rules():
    phone_blocks = [body for prelude, body in css_blocks(dashboard_css()) if prelude == PHONE_MEDIA_QUERY]
    assert len(phone_blocks) == 1
    return css_blocks(phone_blocks[0])


def rules_for(rules, selector):
    """Return the declarations of every rule whose selector list contains the selector."""
    return [body for selectors, body in rules if selector in (s.strip() for s in selectors.split(','))]


def stacks(declarations):
    return re.search(r'flex-direction\s*:\s*column', declarations) is not None


def full_width(declarations):
    return re.search(r'(?<![-\w])width\s*:\s*100%', declarations) is not None


@pytest.fixture
def live_url(event):
    return reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_phone_rules_target_classes_on_the_status_page(organizer_client, live_url):
    html = organizer_client.get(live_url).content.decode()
    page_classes = {name for value in re.findall(r'class="([^"]*)"', html) for name in value.split()}

    phone_classes = {name for selectors, _ in phone_rules() for name in re.findall(r'\.([A-Za-z][\w-]*)', selectors)}

    assert phone_classes
    assert phone_classes - page_classes == set()


@pytest.mark.parametrize('row', STACKED_ROWS)
def test_rows_are_stacked_on_phones_only(row):
    """At 390px the row is stacked, while on desktop it stays side by side."""
    assert any(stacks(body) for body in rules_for(phone_rules(), row))
    assert rules_for(desktop_rules(), row)
    assert not any(stacks(body) for body in rules_for(desktop_rules(), row))


@pytest.mark.parametrize('column', ACTION_COLUMNS)
def test_action_buttons_use_the_full_width_on_phones_only(column):
    """At 390px the buttons fill the width, while on desktop they keep their fixed column."""
    assert any(full_width(body) for body in rules_for(phone_rules(), column))
    assert rules_for(desktop_rules(), column)
    assert not any(full_width(body) for body in rules_for(desktop_rules(), column))
