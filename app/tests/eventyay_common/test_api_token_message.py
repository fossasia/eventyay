from types import SimpleNamespace

from django.utils.safestring import SafeData

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