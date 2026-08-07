"""Integration tests: QR/PDF email placeholders expand end-to-end."""

import datetime

import pytest
from django.core import mail as djmail
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay.base.email import get_email_context, render_order_qr_html
from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product
from eventyay.base.services.mail import mail, render_mail
from eventyay.base.templatetags.rich_text import compile_email_body


@pytest.fixture
def qr_setup():
    with scopes_disabled():
        org = Organizer.objects.create(name='OrgQR', slug='orgqr')
        event = Event.objects.create(
            organizer=org,
            name='QR Event',
            slug='qrevent',
            date_from=now(),
            live=True,
            currency='EUR',
        )
        product = Product.objects.create(
            event=event, name='General', default_price=10, admission=True
        )
        order = Order.objects.create(
            event=event,
            status=Order.STATUS_PAID,
            email='buyer@example.com',
            datetime=now(),
            expires=now() + datetime.timedelta(days=7),
            total=10,
            locale='en',
        )
        pos = OrderPosition.objects.create(
            order=order,
            product=product,
            price=10,
            attendee_name_cached='Ada',
            attendee_name_parts={'full_name': 'Ada'},
            secret='secretticket1234567890',
        )
    return event, order, pos


def _html_from_message(msg) -> str:
    """Extract HTML body from a Django email message (possibly multipart/related)."""
    if not msg.alternatives:
        return ''
    alt = msg.alternatives[0][0]
    if isinstance(alt, str):
        return alt
    # SafeMIMEMultipart from CID inlining — walk for text/html parts.
    parts = []
    for part in alt.walk():
        if part.get_content_type() == 'text/html':
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or 'utf-8'
            parts.append(payload.decode(charset, errors='replace'))
    return '\n'.join(parts)


@pytest.mark.django_db
def test_get_email_context_resolves_qr_with_organizer_scope(qr_setup):
    event, order, pos = qr_setup
    with scope(organizer=event.organizer):
        ctx = get_email_context(event=event, order=order)
    assert 'order_qr' in ctx
    assert 'ticket_qr' in ctx
    assert 'download_tickets_pdf' in ctx
    assert 'data:image/png;base64,' in ctx['order_qr']
    assert '{order_qr}' not in ctx['order_qr']


@pytest.mark.django_db
def test_get_email_context_resolves_qr_without_scope(qr_setup):
    event, order, pos = qr_setup
    ctx = get_email_context(event=event, order=order)
    assert 'order_qr' in ctx, f'missing order_qr; keys={sorted(ctx)}'
    assert 'data:image/png;base64,' in ctx['order_qr']


@pytest.mark.django_db
def test_render_order_qr_html_with_organizer_scope(qr_setup):
    event, order, pos = qr_setup
    with scope(organizer=event.organizer):
        html = render_order_qr_html(order)
    assert 'data:image/png;base64,' in html
    assert 'Ada' in html
    assert '<p>' not in html


@pytest.mark.django_db
def test_mail_send_expands_tiptap_qr_placeholders(qr_setup):
    event, order, pos = qr_setup
    djmail.outbox = []
    template = LazyI18nString(
        '<p>Hello {event_name}</p>'
        '<p>Code {code}</p>'
        '<p><span class="tiptap-placeholder-chip" data-variable="order_qr">{order_qr}</span></p>'
        '<p><span class="tiptap-placeholder-chip" data-variable="download_tickets_pdf">{download_tickets_pdf}</span></p>'
        '<p><span class="tiptap-placeholder-chip" data-variable="ticket_qr">{ticket_qr}</span></p>'
    )
    with scope(organizer=event.organizer):
        ctx = get_email_context(event=event, order=order)
        mail(
            'buyer@example.com',
            'Your tickets',
            template,
            ctx,
            event=event,
            order=order,
            locale='en',
            sync_send=True,
        )
    assert len(djmail.outbox) == 1
    msg = djmail.outbox[0]
    plain = msg.body
    html = _html_from_message(msg)
    assert '{order_qr}' not in plain
    assert '{ticket_qr}' not in plain
    assert '{download_tickets_pdf}' not in plain
    assert '{order_qr}' not in html
    assert '{ticket_qr}' not in html
    assert '{download_tickets_pdf}' not in html
    assert 'cid:' in html or 'data:image/png;base64,' in html
    assert 'Download tickets' in html


@pytest.mark.django_db
def test_compile_email_body_keeps_substituted_qr(qr_setup):
    event, order, pos = qr_setup
    with scope(organizer=event.organizer):
        ctx = get_email_context(event=event, order=order)
    body = (
        '<p>Scan: <span data-variable="order_qr">{order_qr}</span></p>'
        '<p>{download_tickets_pdf}</p>'
    )
    rendered = render_mail(LazyI18nString(body), ctx)
    assert '{order_qr}' not in rendered
    compiled = compile_email_body(rendered)
    assert 'data:image/png;base64,' in compiled
    assert '<img' in compiled
    assert 'class="button"' in compiled
