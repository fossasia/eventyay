from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from django.contrib.messages.storage.base import Message
from django.contrib.messages.storage.cookie import MessageDecoder, MessageEncoder
from django.test import override_settings
from django.urls import reverse
from django.utils.safestring import SafeData
from django_scopes import scopes_disabled

from eventyay.eventyay_common.utils import api_token_created_message


def test_message_has_copy_button_with_full_secret():
    msg = api_token_created_message(SimpleNamespace(token='abc123SECRET'))
    assert isinstance(msg, SafeData)
    assert '<code>abc123SECRET</code>' in msg
    assert 'data-clipboard-text="abc123SECRET"' in msg
    assert 'btn-copy-confirm' in msg


def test_message_escapes_token():
    msg = api_token_created_message(SimpleNamespace(token='<b>x</b>'))
    assert '<b>x</b>' not in msg
    assert '&lt;b&gt;x&lt;/b&gt;' in msg


def test_message_stays_safe_after_session_serialization():
    msg = api_token_created_message(SimpleNamespace(token='abc123SECRET'))
    encoded = MessageEncoder().encode(Message(25, msg))
    decoded = MessageDecoder().decode(encoded)
    assert isinstance(decoded.message, SafeData)
    assert '<code>abc123SECRET</code>' in decoded.message


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_created_token_alert_shows_copy_button_after_redirect(organizer_client, organizer, team):
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    response = organizer_client.post(
        url,
        {
            'team_action': 'tokens',
            'team_id': team.pk,
            f'team-{team.pk}-token-name': 'CI token',
        },
        follow=True,
    )

    with scopes_disabled():
        token = team.tokens.get(name='CI token')

    page = BeautifulSoup(response.content, 'html.parser')
    alerts = [alert for alert in page.select('div.alert') if alert.find('code')]
    assert len(alerts) == 1

    alert = alerts[0]
    code = alert.find('code')
    button = alert.select_one('button.btn-clipboard.btn-copy-confirm')

    assert button is not None
    assert code.get_text() == token.token
    assert button['data-clipboard-text'] == code.get_text()