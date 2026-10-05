import json

import pytest
from django_scopes import scopes_disabled

from eventyay.base.models import Team


@pytest.fixture
def preview_client(client, user, event, settings):
    settings.SITE_URL = 'https://testserver'
    settings.SITE_NETLOC = 'testserver'
    with scopes_disabled():
        team = Team.objects.create(
            organizer=event.organizer,
            name='Mail editors',
            can_change_event_settings=True,
            can_change_submissions=True,
        )
        team.limit_events.add(event)
        team.members.add(user)
    client.force_login(user)
    return client


def request_preview(client, event, endpoint, text):
    if endpoint == 'talk':
        return client.post(
            event.orga_urls.base + 'mails/compose/preview',
            data=json.dumps({'html': f'<p>{text}</p>', 'locale': 'en'}),
            content_type='application/json',
            secure=True,
        )
    return client.post(
        f'/control/event/{event.organizer.slug}/{event.slug}/settings/email/preview',
        {'product': 'mail_text_order_free', 'mail_text_order_free_0': text},
        secure=True,
    )


@pytest.mark.django_db
@pytest.mark.parametrize('endpoint', ['talk', 'tickets'])
@pytest.mark.parametrize('text', ['See you there :}', 'See you there {', '{"talk": "x"}'])
def test_invalid_template_returns_validation_error(preview_client, event, endpoint, text):
    response = request_preview(preview_client, event, endpoint, text)
    assert response.status_code == 400
    assert 'stray { or }' in response.json()['error']


@pytest.mark.django_db
@pytest.mark.parametrize('endpoint', ['talk', 'tickets'])
def test_escaped_braces_and_placeholder_preview(preview_client, event, endpoint):
    response = request_preview(preview_client, event, endpoint, '{{"talk": "x"}} {event}')
    assert response.status_code == 200
    data = response.json()
    html = data['html'] if endpoint == 'talk' else data['msgs']['en']
    assert '{"talk": "x"}' in html
    if endpoint == 'talk':
        assert '<span class="placeholder"' in html
    else:
        assert 'Test Event' in html
