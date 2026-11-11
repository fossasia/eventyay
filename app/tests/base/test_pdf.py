from io import BytesIO

from reportlab.pdfgen.canvas import Canvas

from eventyay.base import pdf


def _create_pdf_buffer(text):
    buffer = BytesIO()
    canvas = Canvas(buffer)
    canvas.drawString(10, 10, text)
    canvas.save()
    buffer.seek(0)
    return buffer


def test_renderer_owns_background_pdf_pages(monkeypatch):
    monkeypatch.setattr(pdf, "get_variables", lambda event: {})
    monkeypatch.setattr(pdf, "get_images", lambda event: {})

    renderer = pdf.Renderer(None, [], _create_pdf_buffer("background"))

    assert len(renderer.bg_pdf.pages) == 1
    assert renderer.bg_pdf.pages[0].extract_text().strip() == "background"


def test_merge_foreground_buffer_uses_writer_owned_pages(monkeypatch):
    monkeypatch.setattr(pdf, "get_variables", lambda event: {})
    monkeypatch.setattr(pdf, "get_images", lambda event: {})

    renderer = pdf.Renderer(None, [], _create_pdf_buffer("background"))
    pages = renderer.merge_foreground_buffer(_create_pdf_buffer("foreground"))

    assert len(pages) == 1
    text = pages[0].extract_text()
    assert "foreground" in text
    assert "background" in text
