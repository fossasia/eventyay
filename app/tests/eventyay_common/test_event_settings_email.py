from pathlib import Path

import pytest

from eventyay.orga.forms.email import CentralMailSettingsForm


@pytest.mark.django_db
def test_event_email_gateway_vendor_mappings(event):
    form = CentralMailSettingsForm(obj=event, attribute_name='settings', prefix='email')

    assert [value for value, _label in form.fields['email_vendor'].choices] == [
        'smtp',
        'sendgrid',
        'gmail_api',
    ]
    assert form.fields['send_grid_api_key'].widget.attrs['data-display-dependency'] == (
        '#id_email-email_vendor_1'
    )
    for field_name in (
        'smtp_host',
        'smtp_port',
        'smtp_username',
        'smtp_password',
        'smtp_use_tls',
        'smtp_use_ssl',
    ):
        assert form.fields[field_name].widget.attrs['data-display-dependency'] == (
            '#id_email-email_vendor_0'
        )

    script_path = (
        Path(__file__).parents[2]
        / 'eventyay'
        / 'static'
        / 'eventyay-common'
        / 'js'
        / 'move-event-email-elements.js'
    )
    script = script_path.read_text(encoding='utf-8')

    assert "moveElement('email-send_grid_api_key', 'email-email_vendor', 1)" in script
    for field_name in (
        'smtp_host',
        'smtp_port',
        'smtp_username',
        'smtp_password',
        'smtp_use_tls',
        'smtp_use_ssl',
    ):
        assert f"moveElement('email-{field_name}', 'email-email_vendor', 0)" in script
    assert "moveGmailPanel('email-email_vendor', 2)" in script
