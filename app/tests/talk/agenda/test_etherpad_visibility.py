"""Tests for public visibility of Etherpad links on session pages.

A pad link is only ever exposed to the public when the platform integration is
on, the event has Etherpad enabled, the session has a pad URL, and the organiser
has opted into public display. Restricted links must never leak.
"""

import pytest
from django_scopes import scope

from eventyay.agenda.etherpad import is_etherpad_publicly_visible
from eventyay.base.settings import GlobalSettingsObject

OPEN_NOTES_LABEL = 'Open collaborative notes'


class _FakeEvent:
    def __init__(self, enabled, public):
        self.feature_flags = {'etherpad_enabled': enabled}
        self.display_settings = {'etherpad_public': public}

    def get_feature_flag(self, feature):
        return self.feature_flags.get(feature, False)


class _FakeSubmission:
    def __init__(self, url):
        self.etherpad_url = url


def _set_platform_enabled(value):
    GlobalSettingsObject().settings.etherpad_enabled = value


@pytest.mark.django_db
def test_visibility_requires_all_conditions():
    _set_platform_enabled(True)
    url = 'https://pad.example.org/p/x'
    assert is_etherpad_publicly_visible(_FakeEvent(True, True), _FakeSubmission(url)) is True
    # No URL configured
    assert is_etherpad_publicly_visible(_FakeEvent(True, True), _FakeSubmission('')) is False
    # Event has Etherpad disabled
    assert is_etherpad_publicly_visible(_FakeEvent(False, True), _FakeSubmission(url)) is False
    # Organiser did not opt into public display
    assert is_etherpad_publicly_visible(_FakeEvent(True, False), _FakeSubmission(url)) is False
    # Platform integration disabled globally -> never public, even with event flags on
    _set_platform_enabled(False)
    assert is_etherpad_publicly_visible(_FakeEvent(True, True), _FakeSubmission(url)) is False


@pytest.mark.django_db
def test_public_talk_page_shows_link_when_enabled(client, event, slot):
    _set_platform_enabled(True)
    with scope(event=event):
        submission = slot.submission
        submission.etherpad_url = 'https://pad.example.org/p/my-pad'
        submission.save()
        event.feature_flags['etherpad_enabled'] = True
        event.display_settings['etherpad_public'] = True
        event.save()

    response = client.get(submission.urls.public, follow=True)
    assert response.status_code == 200
    assert OPEN_NOTES_LABEL in response.text
    assert 'https://pad.example.org/p/my-pad' in response.text


@pytest.mark.django_db
def test_public_talk_page_hides_link_when_not_public(client, event, slot):
    _set_platform_enabled(True)
    with scope(event=event):
        submission = slot.submission
        submission.etherpad_url = 'https://pad.example.org/p/secret-pad'
        submission.save()
        event.feature_flags['etherpad_enabled'] = True
        event.display_settings['etherpad_public'] = False
        event.save()

    response = client.get(submission.urls.public, follow=True)
    assert response.status_code == 200
    assert OPEN_NOTES_LABEL not in response.text
    assert 'secret-pad' not in response.text
