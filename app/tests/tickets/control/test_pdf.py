from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from eventyay.control.views.pdf import BaseEditorView


def test_resize_background_pdf_uses_writer_owned_page(monkeypatch):
    source = BytesIO()
    canvas = Canvas(source, pagesize=(200, 100))
    canvas.drawString(20, 40, 'background')
    canvas.save()
    source.seek(0)

    view = BaseEditorView()
    monkeypatch.setattr(
        view,
        'open_background_pdf',
        lambda cached_file=None: BytesIO(source.getvalue()),
    )

    width_mm, height_mm = 100, 50
    buffer, error = view._resize_background_pdf(width_mm, height_mm)

    assert error is None
    reader = PdfReader(buffer)
    page = reader.pages[0]

    assert float(page.mediabox.width) == pytest.approx(width_mm * mm)
    assert float(page.mediabox.height) == pytest.approx(height_mm * mm)
    assert 'background' in page.extract_text()

def test_resize_background_pdf_returns_error_for_empty_pdf(monkeypatch):
    from pypdf import PdfWriter

    source = BytesIO()
    PdfWriter().write(source)

    view = BaseEditorView()
    monkeypatch.setattr(
        view,
        'open_background_pdf',
        lambda cached_file=None: BytesIO(source.getvalue()),
    )

    buffer, error = view._resize_background_pdf(100, 50)

    assert buffer is None
    assert error is not None
    assert b'"status": "error"' in error.content

