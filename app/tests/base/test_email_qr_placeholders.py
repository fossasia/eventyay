"""Tests for order QR and PDF download email placeholders."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from eventyay.base.email import (
    SimpleFunctionalMailTextPlaceholder,
    download_tickets_button_label,
    get_combined_ticket_output_identifier,
    render_download_tickets_pdf_button,
    render_order_qr_html,
    render_qr_code_img,
    render_ticket_qr_html,
)
from eventyay.base.templatetags.rich_text import (
    build_email_preview_context,
    is_placeholder_html_sample,
    markdown_compile_email,
)


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


def test_markdown_compile_email_preserves_qr_img():
    html = render_qr_code_img('ticket-secret', alt='Ticket QR code')
    compiled = markdown_compile_email(f'Scan this:\n\n{html}')
    assert 'data:image/png;base64,' in compiled
    assert '<img ' in compiled


def test_markdown_compile_email_strips_data_href_on_anchors():
    compiled = markdown_compile_email(
        '<a href="data:text/html,<script>alert(1)</script>" class="button">Click</a>'
    )
    assert 'data:text/html' not in compiled
    assert 'href=' not in compiled or 'href="data:' not in compiled


def test_render_ticket_qr_html(monkeypatch):
    position = SimpleNamespace(ticket_qrcode_content='{"event":"demo","ticket":"abc"}')
    html = render_ticket_qr_html(position)
    assert 'data:image/png;base64,' in html


def test_render_order_qr_html_skips_non_ticket_positions(monkeypatch):
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
    qs.select_related.return_value.filter.return_value.order_by.return_value = [ticket_pos, addon_pos]
    order = SimpleNamespace(all_positions=qs)

    # Avoid depending on django_scopes in this unit test.
    class _NullCtx:
        def __enter__(self):
            return None

        def __exit__(self, *args):
            return False

    monkeypatch.setattr('django_scopes.scopes_disabled', lambda: _NullCtx())

    html = render_order_qr_html(order)
    assert 'Ada Lovelace' in html
    assert 'T-Shirt' not in html
    assert html.count('<img ') == 1
    assert '<p>' not in html  # must stay inline-friendly for Tiptap chips


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
            f'https://shop.example/{kwargs["order"]}/{kwargs["secret"]}/{kwargs["output"]}/?x=1&y=2'
        ),
    )

    html = render_download_tickets_pdf_button(event, order)
    assert 'class="button"' in html
    assert 'href="https://shop.example/ABCDE/secret-value/pdf/?x=1&amp;y=2"' in html
    assert 'Download tickets (PDF)' in html
    compiled = markdown_compile_email(html)
    assert 'class="button"' in compiled
    assert 'https://shop.example/ABCDE/secret-value/pdf/' in compiled


def test_render_download_tickets_button_non_pdf_label(monkeypatch):
    event = MagicMock()
    order = SimpleNamespace(code='ABCDE', secret='secret-value')

    monkeypatch.setattr(
        'eventyay.base.email.get_combined_ticket_output_identifier',
        lambda event: 'applepass',
    )
    monkeypatch.setattr(
        'eventyay.multidomain.urlreverse.build_absolute_uri',
        lambda event, viewname, kwargs=None: (
            f'https://shop.example/{kwargs["order"]}/{kwargs["secret"]}/{kwargs["output"]}/'
        ),
    )

    html = render_download_tickets_pdf_button(event, order)
    assert 'Download tickets (PDF)' not in html
    assert download_tickets_button_label('applepass') in html
    assert 'applepass' in html


def test_order_only_context_resolves_ticket_and_order_qr(monkeypatch):
    """Buyer/order emails have order but no position; QR placeholders must still expand."""
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
    qs.select_related.return_value.filter.return_value.order_by.return_value = [ticket_pos]
    order.all_positions = qs

    class _NullCtx:
        def __enter__(self):
            return None

        def __exit__(self, *args):
            return False

    monkeypatch.setattr('django_scopes.scopes_disabled', lambda: _NullCtx())

    template = 'Ticket: {ticket_qr}\n\nOrder: {order_qr}'
    ctx = {
        'ticket_qr': render_order_qr_html(order),
        'order_qr': render_order_qr_html(order),
    }
    body = render_mail(LazyI18nString(template), ctx)
    assert '{ticket_qr}' not in body
    assert '{order_qr}' not in body
    assert 'data:image/png;base64,' in body
    assert body == template.format_map(TolerantDict({k: str(v) for k, v in ctx.items()}))
    assert 'data:image/png;base64,' in markdown_compile_email(body)


def test_tolerant_dict_keeps_braces_for_missing_placeholders():
    from eventyay.base.services.mail import TolerantDict

    assert 'Order QR: {order_qr}'.format_map(TolerantDict({'event': 'Demo'})) == 'Order QR: {order_qr}'


def test_get_email_context_resolves_qr_when_earlier_placeholder_hits_scope_error(monkeypatch):
    """A ScopeError from an earlier placeholder must not drop QR placeholders."""
    from django_scopes.exceptions import ScopeError

    from eventyay.base.email import (
        SimpleFunctionalMailTextPlaceholder,
        get_email_context,
        render_qr_code_img,
    )

    event = MagicMock()
    order = SimpleNamespace(code='ABCDE', secret='secret')
    qr_html = render_qr_code_img('{"ticket":"one"}', alt='Ticket QR code')
    button_html = '<a href="https://example.com" class="button">Download tickets (PDF)</a>'

    placeholders = [
        SimpleFunctionalMailTextPlaceholder(
            'name',
            ['position_or_address'],
            lambda position_or_address: (_ for _ in ()).throw(ScopeError('organizer')),
            'John',
        ),
        SimpleFunctionalMailTextPlaceholder('order_qr', ['order'], lambda order: qr_html, qr_html),
        SimpleFunctionalMailTextPlaceholder('ticket_qr', ['order'], lambda order: qr_html, qr_html),
        SimpleFunctionalMailTextPlaceholder(
            'download_tickets_pdf',
            ['order', 'event'],
            lambda order, event: button_html,
            button_html,
        ),
    ]

    monkeypatch.setattr(
        'eventyay.base.email.register_mail_placeholders.send',
        lambda sender: [(None, placeholders)],
    )
    order.invoice_address = MagicMock()

    ctx = get_email_context(event=event, order=order)
    assert 'order_qr' in ctx
    assert 'ticket_qr' in ctx
    assert 'download_tickets_pdf' in ctx
    assert 'name' not in ctx
    assert 'data:image/png;base64,' in ctx['order_qr']


def test_expand_email_variable_chips_without_braces():
    """Chips whose text is bare ``order_qr`` (no braces) must still resolve."""
    from eventyay.base.services.mail import expand_email_variable_chips, render_mail
    from i18nfield.strings import LazyI18nString

    qr = render_qr_code_img('secret', alt='Ticket QR code')
    button = '<a href="https://example.com" class="button">Download tickets (PDF)</a>'
    body = (
        '<p>Order QR: <span class="tiptap-placeholder-chip" data-variable="order_qr">order_qr</span></p>'
        '<p>Ticket QR: <span data-variable="ticket_qr">ticket_qr</span></p>'
        '<p>Download Ticket: <span data-variable="download_tickets_pdf">download_tickets_pdf</span></p>'
    )
    ctx = {
        'order_qr': qr,
        'ticket_qr': qr,
        'download_tickets_pdf': button,
    }
    expanded = expand_email_variable_chips(body, ctx)
    assert 'data-variable=' not in expanded
    assert '>order_qr<' not in expanded
    assert '>ticket_qr<' not in expanded
    assert '>download_tickets_pdf<' not in expanded
    assert expanded.count('<img') == 2
    assert 'class="button"' in expanded
    assert 'Download tickets (PDF)' in expanded

    rendered = render_mail(LazyI18nString(body), ctx)
    assert 'data:image/png;base64,' in rendered
    assert '>download_tickets_pdf<' not in rendered
    assert 'class="button"' in rendered


def test_expand_email_variable_chips_leaves_unknown_keys():
    from eventyay.base.services.mail import expand_email_variable_chips

    body = '<span data-variable="order_qr">order_qr</span>'
    assert expand_email_variable_chips(body, {'event': 'Demo'}) == body
    assert expand_email_variable_chips(body, {'order_qr': 'order_qr'}) == body
    assert expand_email_variable_chips(body, {'order_qr': '{order_qr}'}) == body


def test_is_placeholder_html_sample_detects_qr_and_button():
    assert is_placeholder_html_sample('<img src="data:image/png;base64,abc" alt="QR">')
    assert is_placeholder_html_sample('<a href="https://example.com" class="button">Download</a>')
    assert is_placeholder_html_sample('<p><strong>Ada</strong></p><img src="data:image/png;base64,abc">')
    assert is_placeholder_html_sample('<strong>Ada</strong><br><img src="data:image/png;base64,abc">')
    assert not is_placeholder_html_sample('F8VVL')
    assert not is_placeholder_html_sample('https://example.com/order')


def test_expand_email_preview_placeholders_keeps_qr_and_button_html():
    from unittest.mock import MagicMock, patch

    from eventyay.base.templatetags.rich_text import expand_email_preview_placeholders

    qr_sample = render_qr_code_img('secret', alt='Ticket QR code')
    button_sample = '<a href="https://example.com" class="button">Download tickets (PDF)</a>'
    placeholders = {
        'code': SimpleFunctionalMailTextPlaceholder('code', ['order'], lambda order: order.code, 'F8VVL'),
        'order_qr': SimpleFunctionalMailTextPlaceholder(
            'order_qr', ['order'], lambda order: qr_sample, qr_sample
        ),
        'download_tickets_pdf': SimpleFunctionalMailTextPlaceholder(
            'download_tickets_pdf',
            ['order', 'event'],
            lambda order, event: button_sample,
            button_sample,
        ),
    }
    event = MagicMock()
    event.settings.locale = 'en'
    event.settings.locales = ['en']
    event.settings.region = None
    body = (
        '<p>Code {code}</p>'
        '<p><span data-variable="order_qr">{order_qr}</span></p>'
        '<p>{download_tickets_pdf}</p>'
    )

    with patch('eventyay.base.email.get_available_placeholders', return_value=placeholders):
        preview = expand_email_preview_placeholders(body, event, locale='en')

    assert '{order_qr}' not in preview
    assert '&lt;img' not in preview
    assert '<img' in preview
    assert 'data:image/png;base64,' in preview
    assert 'class="button"' in preview
    assert 'placeholder' in preview  # plain samples still wrapped
    assert 'F8VVL' in preview


def test_tiptap_compile_keeps_inline_order_qr_inside_chip():
    from eventyay.base.templatetags.rich_text import compile_email_body

    qr = (
        '<strong>Ada</strong><br>'
        + render_qr_code_img('{"ticket":"one"}', alt='Ticket QR code')
    )
    button = '<a href="https://shop.example/pdf/" class="button">Download tickets (PDF)</a>'
    body = (
        f'<p>QR <span class="tiptap-placeholder-chip" data-variable="order_qr">{qr}</span></p>'
        f'<p>PDF <span data-variable="download_tickets_pdf">{button}</span></p>'
    )
    compiled = compile_email_body(body)
    assert '{order_qr}' not in compiled
    assert 'data:image/png;base64,' in compiled
    assert '<img' in compiled
    # Chip should still wrap the inline QR (not hoisted out as an empty span).
    assert 'data-variable="order_qr"' in compiled
    assert 'class="button"' in compiled
    assert 'Download tickets (PDF)' in compiled


def test_get_combined_ticket_output_identifier_prefers_pdf():
    event = MagicMock()

    class PdfProvider:
        identifier = 'pdf'
        is_enabled = True

    class OtherProvider:
        identifier = 'applepass'
        is_enabled = True

    with patch('eventyay.base.signals.register_ticket_outputs.send') as send:
        send.return_value = [
            (None, lambda e: OtherProvider()),
            (None, lambda e: PdfProvider()),
        ]
        assert get_combined_ticket_output_identifier(event) == 'pdf'


def test_get_combined_ticket_output_identifier_falls_back_to_first_enabled():
    event = MagicMock()

    class OtherProvider:
        identifier = 'applepass'
        is_enabled = True

    class DisabledPdf:
        identifier = 'pdf'
        is_enabled = False

    with patch('eventyay.base.signals.register_ticket_outputs.send') as send:
        send.return_value = [
            (None, lambda e: DisabledPdf()),
            (None, lambda e: OtherProvider()),
        ]
        assert get_combined_ticket_output_identifier(event) == 'applepass'


def test_build_email_preview_context_keeps_html_samples():
    event = MagicMock()
    qr_sample = render_qr_code_img('secret', alt='Ticket QR code')
    button_sample = '<a href="https://example.com" class="button">Download tickets (PDF)</a>'
    placeholders = {
        'code': SimpleFunctionalMailTextPlaceholder('code', ['order'], lambda order: order.code, 'F8VVL'),
        'ticket_qr': SimpleFunctionalMailTextPlaceholder(
            'ticket_qr', ['order'], lambda order: qr_sample, qr_sample
        ),
        'download_tickets_pdf': SimpleFunctionalMailTextPlaceholder(
            'download_tickets_pdf',
            ['order', 'event'],
            lambda order, event: button_sample,
            button_sample,
        ),
    }

    with patch(
        'eventyay.base.email.get_available_placeholders',
        return_value=placeholders,
    ):
        ctx = build_email_preview_context(event, ['event', 'order'])

    assert ctx['ticket_qr'] == qr_sample
    assert ctx['download_tickets_pdf'] == button_sample
    assert 'placeholder' in ctx['code']
    assert 'F8VVL' in ctx['code']
    assert '<span' in ctx['code']
