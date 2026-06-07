"""Tests for the Etherpad collaborative-notes service.

These cover safe pad-name generation, URL validation, link-only vs API mode,
and the overwrite protection that prevents existing notes from being replaced
without confirmation.
"""

import pytest
from django.core.exceptions import ValidationError

from eventyay.base.services.etherpad import (
    EtherpadConfigurationError,
    EtherpadError,
    build_pad_name,
    build_pad_url,
    generate_pad_for_submission,
    sanitize_pad_segment,
    validate_etherpad_url,
)
from eventyay.base.settings import GlobalSettingsObject


class _FakeSubmission:
    def __init__(self, code, etherpad_url=None):
        self.code = code
        self.etherpad_url = etherpad_url


class _FakeEvent:
    def __init__(self, slug):
        self.slug = slug


def test_sanitize_pad_segment_strips_unsafe_characters():
    assert sanitize_pad_segment('My Talk: Notes/Draft!') == 'My-Talk-Notes-Draft'
    assert sanitize_pad_segment('  spaces  ') == 'spaces'
    assert sanitize_pad_segment('a@@@b') == 'a-b'


def test_build_pad_name_uses_stable_pattern_and_token():
    event = _FakeEvent('djangocon')
    submission = _FakeSubmission('ABC123')
    name = build_pad_name(event, submission, pattern='{event}-{submission}-{token}', token='tok12345')
    assert name == 'djangocon-ABC123-tok12345'
    # only safe characters
    assert all(c.isalnum() or c in '-_' for c in name)


def test_build_pad_name_does_not_leak_unsafe_title():
    # Even with a hostile pattern, the result must stay URL-safe.
    event = _FakeEvent('ev')
    submission = _FakeSubmission('S1')
    name = build_pad_name(event, submission, pattern='{event}/../{submission} <script>', token='zzz')
    assert '/' not in name
    assert '<' not in name and '>' not in name


def test_build_pad_name_is_length_limited():
    event = _FakeEvent('e' * 80)
    submission = _FakeSubmission('S' * 80)
    name = build_pad_name(event, submission, pattern='{event}-{submission}-{token}')
    assert len(name) <= 50


def test_build_pad_url_joins_safely():
    assert build_pad_url('https://pad.example.org', 'my-pad') == 'https://pad.example.org/p/my-pad'
    assert build_pad_url('https://pad.example.org/', 'my-pad') == 'https://pad.example.org/p/my-pad'


def test_validate_etherpad_url_accepts_http_and_https():
    validate_etherpad_url('https://pad.example.org')
    validate_etherpad_url('http://localhost:9001')
    validate_etherpad_url('')  # empty is allowed (optional)


def test_validate_etherpad_url_rejects_invalid():
    with pytest.raises(ValidationError):
        validate_etherpad_url('not-a-url')
    with pytest.raises(ValidationError):
        validate_etherpad_url('ftp://pad.example.org')


@pytest.mark.django_db
def test_generate_link_only_mode_without_api_key(event, submission):
    gs = GlobalSettingsObject().settings
    gs.etherpad_enabled = True
    gs.etherpad_base_url = 'https://pad.example.org'
    gs.etherpad_api_key = ''
    gs.etherpad_pad_name_pattern = '{event}-{submission}-{token}'

    url = generate_pad_for_submission(event, submission)
    assert url.startswith('https://pad.example.org/p/')
    assert event.slug in url
    assert submission.code in url


@pytest.mark.django_db
def test_generate_uses_api_when_key_present(event, submission, monkeypatch):
    gs = GlobalSettingsObject().settings
    gs.etherpad_enabled = True
    gs.etherpad_base_url = 'https://pad.example.org'
    gs.etherpad_api_key = 'secret-key'
    gs.etherpad_pad_name_pattern = '{event}-{submission}-{token}'

    calls = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {'code': 0, 'message': 'ok'}

    def fake_get(endpoint, params=None, timeout=None):
        calls['endpoint'] = endpoint
        calls['params'] = params
        return _Resp()

    monkeypatch.setattr('eventyay.base.services.etherpad.requests.get', fake_get)

    url = generate_pad_for_submission(event, submission)
    assert 'createPad' in calls['endpoint']
    assert calls['params']['apikey'] == 'secret-key'
    assert url.startswith('https://pad.example.org/p/')


@pytest.mark.django_db
def test_generate_refuses_overwrite_without_force(event, submission):
    gs = GlobalSettingsObject().settings
    gs.etherpad_enabled = True
    gs.etherpad_base_url = 'https://pad.example.org'
    gs.etherpad_api_key = ''

    submission.etherpad_url = 'https://pad.example.org/p/existing'
    with pytest.raises(EtherpadError):
        generate_pad_for_submission(event, submission)

    # With force it succeeds and produces a fresh URL.
    url = generate_pad_for_submission(event, submission, force=True)
    assert url.startswith('https://pad.example.org/p/')


@pytest.mark.django_db
def test_generate_requires_platform_enabled(event, submission):
    gs = GlobalSettingsObject().settings
    gs.etherpad_enabled = False
    with pytest.raises(EtherpadConfigurationError):
        generate_pad_for_submission(event, submission)


@pytest.mark.django_db
def test_generate_requires_base_url(event, submission):
    gs = GlobalSettingsObject().settings
    gs.etherpad_enabled = True
    gs.etherpad_base_url = ''
    with pytest.raises(EtherpadConfigurationError):
        generate_pad_for_submission(event, submission)
