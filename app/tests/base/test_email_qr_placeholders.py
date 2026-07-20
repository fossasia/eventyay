"""Tests for order QR and PDF download email placeholders."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from eventyay.base.email import (
    render_download_tickets_pdf_button,
    render_order_qr_html,
    render_qr_code_img,
    render_ticket_qr_html,
)
from eventyay.common.sanitizers import sanitize_email_html


def test_render_qr_code_img_uses_data_uri():
    html = render_qr_code_img('{"ticket":"secret"}', alt='Ticket QR code')
    assert html.startswith('<img src="data:image/png;base64,')
    assert 'alt="Ticket QR code"' in html
    assert 'width="160"' in html
    assert 'height="160"' in html


def test_render_qr_code_img_escapes_alt():
    html = render_qr_code_img('payload', alt='"><script>alert(1)</script>')
    assert '<script>' not in html
    assert '&lt;script&gt;' in html


def test_sanitize_preserves_qr_img():
    html = render_qr_code_img('ticket-secret', alt='Ticket QR code')
    assert 'data:image/png;base64,' in sanitize_email_html(html)


def test_render_ticket_qr_html(monkeypatch):
    position = SimpleNamespace(ticket_qrcode_content='{"event":"demo","ticket":"abc"}')
    html = render_ticket_qr_html(position)
    assert 'data:image/png;base64,' in html


def test_render_order_qr_html_skips_non_ticket_positions():
    ticket_pos = SimpleNamespace(
        generate_ticket=True,
        attendee_name='Ada Lovelace',
        product=SimpleNamespace(name='General'),
        ticket_qrcode_content='{"ticket":"one"}',
        positionid=1,
    )
    addon_pos = SimpleNamespace(
        generate_ticket=False,
        attendee_name=None,
        product=SimpleNamespace(name='T-Shirt'),
        ticket_qrcode_content='{"ticket":"two"}',
        positionid=2,
    )
    qs = MagicMock()
    qs.select_related.return_value.order_by.return_value = [ticket_pos, addon_pos]
    order = SimpleNamespace(positions=qs)

    html = render_order_qr_html(order)
    assert 'Ada Lovelace' in html
    assert 'T-Shirt' not in html
    assert html.count('<img ') == 1


def test_render_download_tickets_pdf_button(monkeypatch):
    event = MagicMock()
    order = SimpleNamespace(code='ABCDE', secret='secret-value')

    monkeypatch.setattr(
        'eventyay.base.email.get_combined_ticket_output_identifier',
        lambda event: 'pdf',
    )
    monkeypatch.setattr(
        'eventyay.multidomain.urlreverse.build_absolute_uri',
        lambda event, viewname, kwargs=None: (
            f'https://shop.example/{kwargs["order"]}/{kwargs["secret"]}/{kwargs["output"]}/'
        ),
    )

    html = render_download_tickets_pdf_button(event, order)
    assert 'class="button"' in html
    assert 'https://shop.example/ABCDE/secret-value/pdf/' in html
    assert 'Download tickets (PDF)' in html
    assert 'class="button"' in sanitize_email_html(html)


def test_tiptap_chips_resolve_with_order_only_context():
    """Buyer/order emails have order but no position; chips must still expand."""
    from i18nfield.strings import LazyI18nString

    from eventyay.base.services.mail import TolerantDict, render_mail

    order = SimpleNamespace()
    qs = MagicMock()
    ticket_pos = SimpleNamespace(
        generate_ticket=True,
        attendee_name='Ada',
        product=SimpleNamespace(name='General'),
        ticket_qrcode_content='{"ticket":"one"}',
        positionid=1,
    )
    qs.select_related.return_value.order_by.return_value = [ticket_pos]
    order.positions = qs

    tip = (
        '<p><span data-variable="ticket_qr" class="tiptap-placeholder-chip">{ticket_qr}</span></p>'
        '<p><span data-variable="order_qr" class="tiptap-placeholder-chip">{order_qr}</span></p>'
    )
    ctx = {
        'ticket_qr': render_order_qr_html(order),
        'order_qr': render_order_qr_html(order),
    }
    body = render_mail(LazyI18nString(tip), ctx)
    assert '{ticket_qr}' not in body
    assert '{order_qr}' not in body
    assert '>ticket_qr<' not in body
    assert '>order_qr<' not in body
    assert 'data:image/png;base64,' in body
    assert body == tip.format_map(TolerantDict({k: str(v) for k, v in ctx.items()}))

