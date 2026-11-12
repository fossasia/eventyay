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
    # `text` may be a list with one string per page.
    texts = text if isinstance(text, list) else [text] * pages
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    for page_text in texts:
        c.drawString(20, 100, page_text)
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


def _text_position(page, needle):
    # Position of the first text run containing `needle`, in page space.
    found = []

    def visit(text, cm, tm, font_dict, font_size):
        if needle in text:
            x, y = tm[4], tm[5]
            found.append((cm[0] * x + cm[2] * y + cm[4], cm[1] * x + cm[3] * y + cm[5]))

    page.extract_text(visitor_text=visit)
    return found[0]


@pytest.mark.parametrize('rotate', [0, 90])
def test_background_is_merged_under_foreground(rotate):
    renderer = _renderer(_make_pdf('BACKGROUNDTEXT', rotate=rotate))
    # The foreground gets the size draw_page gives it: swapped for a rotated background.
    width, height = (200, 300) if rotate else (300, 200)
    pages = renderer.merge_foreground_buffer(_make_pdf('FOREGROUNDTEXT', width=width, height=height))
    assert len(pages) == 1
    page = pages[0]

    # Background content comes first in the stream, so the foreground is painted on top.
    content = page.get_contents().get_data()
    assert content.index(b'BACKGROUNDTEXT') < content.index(b'FOREGROUNDTEXT')

    # The background text must land inside the output page.
    x, y = _text_position(page, 'BACKGROUNDTEXT')
    assert 0 <= x <= float(page.mediabox.width)
    assert 0 <= y <= float(page.mediabox.height)


def test_background_is_merged_into_every_foreground_page():
    renderer = _renderer(_make_pdf('BACKGROUNDTEXT', pages=3))
    expected_texts = ['FIRSTPAGE', 'SECONDPAGE', 'THIRDPAGE']
    pages = renderer.merge_foreground_buffer(_make_pdf(expected_texts))
    assert len(pages) == 3
    for page, expected in zip(pages, expected_texts):
        text = _page_text(page)
        assert 'BACKGROUNDTEXT' in text
        assert expected in text


def test_only_first_background_page_is_kept():
    renderer = _renderer(_make_pdf(pages=3))
    assert len(renderer.bg_pdf.pages) == 1


def test_no_background_returns_foreground_pages():
    renderer = _renderer(None)
    pages = renderer.merge_foreground_buffer(_make_pdf('FOREGROUNDTEXT'))
    assert len(pages) == 1
    assert 'FOREGROUNDTEXT' in _page_text(pages[0])


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
