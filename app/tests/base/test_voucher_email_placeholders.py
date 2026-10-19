"""Voucher bulk-email placeholders."""

import datetime
import json
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.email import format_voucher_list, get_available_placeholders, voucher_redemption_urls
from eventyay.base.models import Event, Organizer, Voucher
from eventyay.base.templatetags.rich_text import (
    _PREVIEW_PLACEHOLDER_CONTEXT,
    expand_email_preview_placeholders,
)
from eventyay.common.forms.widgets import EmailEditorWidget
from eventyay.control.forms.vouchers import VoucherBulkForm
from eventyay.control.views.event import EditorEmailPreview


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


def test_voucher_list_puts_each_code_on_its_own_line():
    rendered = format_voucher_list(['CODEAAA1', 'A&B'])

    assert rendered == '<span>CODEAAA1<br>A&amp;B</span>'


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


@pytest.fixture
def event():
    organizer = Organizer.objects.create(name='CCC', slug='ccc-vouchers')
    return Event.objects.create(
        organizer=organizer,
        name='30C3',
        slug='30c3',
        date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.UTC),
    )


def _url_sample(event, parameters):
    return str(get_available_placeholders(event, parameters)['url'].render_sample(event))


def _preview_text(event, preview_context=None):
    rendered = expand_email_preview_placeholders('<p>{url}</p>', event, preview_context=preview_context)
    return BeautifulSoup(rendered, 'html.parser').get_text().strip()


@pytest.mark.django_db
def test_url_only_preview_keeps_the_order_sample(event):
    assert _preview_text(event) == _url_sample(event, list(_PREVIEW_PLACEHOLDER_CONTEXT))


@pytest.mark.django_db
def test_voucher_preview_context_renders_the_shop_url_for_url(event):
    shop_url = _url_sample(event, ['event', 'voucher_list', 'name'])

    assert _preview_text(event, 'voucher') == shop_url
    assert shop_url != _url_sample(event, list(_PREVIEW_PLACEHOLDER_CONTEXT))


@pytest.mark.django_db
def test_other_preview_contexts_keep_the_order_sample(event):
    assert _preview_text(event, 'order') == _preview_text(event)


@pytest.mark.django_db
def test_bulk_voucher_form_asks_for_voucher_preview_context(event):
    with scopes_disabled():
        form = VoucherBulkForm(instance=Voucher(event=event))
    preview_url = form.fields['send_message'].widget.attrs['data-tiptap-preview-url']

    assert (
        preview_url
        == reverse(
            'control:event.editor.email.preview',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )
        + '?context=voucher'
    )


@pytest.mark.django_db
def test_shared_preview_endpoint_honors_voucher_context(event):
    request = RequestFactory().post(
        '/editor/email-preview?context=voucher',
        data=json.dumps({'html': '<p>{url}</p>'}),
        content_type='application/json',
    )
    request.event = event

    response = EditorEmailPreview()._handle_json(request)
    rendered = json.loads(response.content)['html']

    assert response.status_code == 200
    assert BeautifulSoup(rendered, 'html.parser').get_text().strip() == _url_sample(
        event, ['event', 'voucher_list', 'name']
    )


def test_voucher_url_chip_expands():
    from eventyay.base.services.mail import expand_email_variable_chips

    body = '<span class="tiptap-placeholder-chip" data-variable="voucher_url">{voucher_url}</span>'
    expanded = expand_email_variable_chips(
        body,
        {'voucher_url': '<a href="https://shop.example/redeem/?voucher=ABC">link</a>'},
    )

    assert expanded == '<a href="https://shop.example/redeem/?voucher=ABC">link</a>'
