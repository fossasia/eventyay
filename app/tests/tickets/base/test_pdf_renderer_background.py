from io import BytesIO
from unittest import mock

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from eventyay.base import pdf as pdf_module
from eventyay.base.pdf import Renderer
from eventyay.control.views.pdf import BaseEditorView


def _make_pdf(text='background', width=300, height=200, rotate=0, pages=1):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    for _ in range(pages):
        c.drawString(20, 100, text)
        c.showPage()
    c.save()
    buf.seek(0)
    if rotate:
        writer = PdfWriter(clone_from=PdfReader(buf))
        writer.pages[0].rotate(rotate)
        out = BytesIO()
        writer.write(out)
        out.seek(0)
        return out
    return buf


def _renderer(background):
    with (
        mock.patch.object(pdf_module, 'get_variables', return_value={}),
        mock.patch.object(pdf_module, 'get_images', return_value={}),
    ):
        return Renderer(mock.Mock(), [], background)


def _page_text(page):
    out = BytesIO()
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(out)
    out.seek(0)
    return PdfReader(out).pages[0].extract_text()


@pytest.mark.parametrize('rotate', [0, 90])
def test_background_is_merged_under_foreground(rotate):
    renderer = _renderer(_make_pdf('BACKGROUNDTEXT', rotate=rotate))
    pages = renderer.merge_foreground_buffer(_make_pdf('FOREGROUNDTEXT'))
    assert len(pages) == 1
    text = _page_text(pages[0])
    assert 'BACKGROUNDTEXT' in text
    assert 'FOREGROUNDTEXT' in text


def test_background_is_merged_into_every_foreground_page():
    renderer = _renderer(_make_pdf('BACKGROUNDTEXT', pages=3))
    pages = renderer.merge_foreground_buffer(_make_pdf('FOREGROUNDTEXT', pages=3))
    assert len(pages) == 3
    for page in pages:
        text = _page_text(page)
        assert 'BACKGROUNDTEXT' in text
        assert 'FOREGROUNDTEXT' in text


def test_only_first_background_page_is_kept():
    renderer = _renderer(_make_pdf(pages=3))
    assert len(renderer.bg_pdf.pages) == 1


def test_no_background_returns_foreground_pages():
    renderer = _renderer(None)
    assert len(renderer.merge_foreground_buffer(_make_pdf())) == 1


def test_resize_background_pdf_scales_page_and_keeps_content():
    class View(BaseEditorView):
        def open_background_pdf(self, cached_file=None):
            return _make_pdf('BACKGROUNDTEXT', width=300, height=200)

    buffer, error = View()._resize_background_pdf(100, 50)

    assert error is None
    page = PdfReader(buffer).pages[0]
    assert float(page.mediabox.width) == pytest.approx(100 * mm, abs=0.5)
    assert float(page.mediabox.height) == pytest.approx(50 * mm, abs=0.5)
    assert 'BACKGROUNDTEXT' in page.extract_text()
