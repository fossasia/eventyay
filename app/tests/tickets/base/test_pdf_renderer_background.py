from io import BytesIO
from unittest import mock

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from eventyay.base import pdf as pdf_module
from eventyay.base.pdf import Renderer


def _make_pdf(width=300, height=200, rotate=0):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.drawString(20, 100, 'background')
    c.showPage()
    c.save()
    buf.seek(0)
    if rotate:
        from pypdf import PdfWriter

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


@pytest.mark.parametrize('rotate', [0, 90])
def test_background_is_merged_under_foreground(rotate):
    renderer = _renderer(_make_pdf(rotate=rotate))
    pages = renderer.merge_foreground_buffer(_make_pdf())
    assert len(pages) == 1
    out = BytesIO()
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_page(pages[0])
    writer.write(out)
    out.seek(0)
    assert len(PdfReader(out).pages) == 1


def test_no_background_returns_foreground_pages():
    renderer = _renderer(None)
    assert len(renderer.merge_foreground_buffer(_make_pdf())) == 1
