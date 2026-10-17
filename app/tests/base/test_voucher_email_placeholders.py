"""Voucher bulk-email placeholders."""

from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError

from eventyay.base.email import voucher_redemption_urls
from eventyay.common.forms.widgets import EmailEditorWidget
from eventyay.control.forms.vouchers import VoucherBulkForm


def test_voucher_redemption_urls_link_each_code(monkeypatch):
    def fake_uri(event, urlname, kwargs=None):
        assert urlname == 'presale:event.redeem'
        return 'https://shop.example/ccc/30c3/redeem/'

    monkeypatch.setattr('eventyay.multidomain.urlreverse.build_absolute_uri', fake_uri)

    rendered = voucher_redemption_urls(SimpleNamespace(), ['ABCDE', 'A B&C'])

    assert rendered == (
        '<a href="https://shop.example/ccc/30c3/redeem/?voucher=ABCDE">'
        'https://shop.example/ccc/30c3/redeem/?voucher=ABCDE</a>'
        '<br>'
        '<a href="https://shop.example/ccc/30c3/redeem/?voucher=A%20B%26C">'
        'https://shop.example/ccc/30c3/redeem/?voucher=A%20B%26C</a>'
    )


def _recipients_form(raw):
    form = VoucherBulkForm.__new__(VoucherBulkForm)
    form.cleaned_data = {'send_recipients': raw}
    return form


def test_negative_recipient_count_is_rejected():
    form = _recipients_form('email,number\nfoo@example.com,-1\nbar@example.com,3')

    with pytest.raises(ValidationError, match='at least 1'):
        VoucherBulkForm.clean_send_recipients(form)


def test_zero_recipient_count_is_rejected():
    form = _recipients_form('email,number\nfoo@example.com,0')

    with pytest.raises(ValidationError, match='at least 1'):
        VoucherBulkForm.clean_send_recipients(form)


def test_positive_recipient_count_is_kept():
    form = _recipients_form('email,number\nfoo@example.com,2')

    recipients = VoucherBulkForm.clean_send_recipients(form)

    assert recipients[0].number == 2
    assert recipients[0].email == 'foo@example.com'


def test_bulk_voucher_email_uses_tiptap_editor():
    field = VoucherBulkForm.base_fields['send_message']
    assert isinstance(field.widget, EmailEditorWidget)
    assert field.widget.attrs['data-tiptap-profile'] == 'email'
    assert '{voucher_url}' in field.initial


def test_voucher_url_chip_expands():
    from eventyay.base.services.mail import expand_email_variable_chips

    body = '<span class="tiptap-placeholder-chip" data-variable="voucher_url">{voucher_url}</span>'
    expanded = expand_email_variable_chips(
        body,
        {'voucher_url': '<a href="https://shop.example/redeem/?voucher=ABC">link</a>'},
    )

    assert expanded == '<a href="https://shop.example/redeem/?voucher=ABC">link</a>'
