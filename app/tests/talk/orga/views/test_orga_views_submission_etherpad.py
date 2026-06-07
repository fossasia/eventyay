"""Tests for organiser-facing Etherpad controls on sessions.

Covers the auto-generate endpoint (permissions, overwrite confirmation, event
gating) and the presence/absence of the session Etherpad field in the edit form.
"""

import pytest
from django_scopes import scope

from eventyay.base.settings import GlobalSettingsObject


def _enable_platform_etherpad(api_key=''):
    gs = GlobalSettingsObject().settings
    gs.etherpad_enabled = True
    gs.etherpad_base_url = 'https://pad.example.org'
    gs.etherpad_api_key = api_key
    gs.etherpad_pad_name_pattern = '{event}-{submission}-{token}'


def _enable_event_etherpad(event, auto_generate=True):
    event.feature_flags['etherpad_enabled'] = True
    event.feature_flags['etherpad_auto_generate'] = auto_generate
    event.save()


@pytest.mark.django_db
def test_orga_can_generate_etherpad_link(orga_client, event, submission):
    _enable_platform_etherpad()
    with scope(event=event):
        _enable_event_etherpad(event)

    response = orga_client.post(submission.orga_urls.etherpad_generate, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        submission.refresh_from_db()
        assert submission.etherpad_url
        assert submission.etherpad_url.startswith('https://pad.example.org/p/')


@pytest.mark.django_db
def test_existing_link_not_overwritten_without_force(orga_client, event, submission):
    _enable_platform_etherpad()
    with scope(event=event):
        _enable_event_etherpad(event)
        submission.etherpad_url = 'https://pad.example.org/p/original'
        submission.save()

    orga_client.post(submission.orga_urls.etherpad_generate, follow=True)
    with scope(event=event):
        submission.refresh_from_db()
        assert submission.etherpad_url == 'https://pad.example.org/p/original'


@pytest.mark.django_db
def test_existing_link_replaced_with_force(orga_client, event, submission):
    _enable_platform_etherpad()
    with scope(event=event):
        _enable_event_etherpad(event)
        submission.etherpad_url = 'https://pad.example.org/p/original'
        submission.save()

    orga_client.post(submission.orga_urls.etherpad_generate, {'force': 'true'}, follow=True)
    with scope(event=event):
        submission.refresh_from_db()
        assert submission.etherpad_url != 'https://pad.example.org/p/original'
        assert submission.etherpad_url.startswith('https://pad.example.org/p/')


@pytest.mark.django_db
def test_generation_blocked_when_event_disabled(orga_client, event, submission):
    _enable_platform_etherpad()
    # event flag left disabled
    orga_client.post(submission.orga_urls.etherpad_generate, follow=True)
    with scope(event=event):
        submission.refresh_from_db()
        assert not submission.etherpad_url


@pytest.mark.django_db
def test_anonymous_cannot_generate(client, event, submission):
    _enable_platform_etherpad()
    with scope(event=event):
        _enable_event_etherpad(event)

    response = client.post(submission.orga_urls.etherpad_generate)
    assert response.status_code in (302, 403, 404)
    with scope(event=event):
        submission.refresh_from_db()
        assert not submission.etherpad_url


@pytest.mark.django_db
def test_edit_form_shows_field_when_enabled(orga_client, event, submission):
    _enable_platform_etherpad()
    with scope(event=event):
        _enable_event_etherpad(event)

    response = orga_client.get(submission.orga_urls.edit, follow=True)
    assert response.status_code == 200
    assert 'etherpad_url' in response.text


@pytest.mark.django_db
def test_edit_form_hides_field_when_disabled(orga_client, event, submission):
    response = orga_client.get(submission.orga_urls.edit, follow=True)
    assert response.status_code == 200
    assert 'id_etherpad_url' not in response.text
