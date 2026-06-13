from eventyay.base import pdf
from eventyay.base.pdf import Renderer


class CanvasSpy:
    def __init__(self):
        self.draw_calls = []

    def drawImage(self, *args, **kwargs):
        self.draw_calls.append((args, kwargs))


class FailingImageReader:
    def __init__(self, image):
        self.image = image

    def resize(self, width, height, dpi):
        raise OSError('broken image')


class ResizingImageReader:
    def __init__(self, image):
        self.image = image

    def resize(self, width, height, dpi):
        return 12, 34


def test_draw_poweredby_skips_image_when_resize_fails(monkeypatch):
    monkeypatch.setattr(pdf.finders, 'find', lambda path: 'broken.png')
    monkeypatch.setattr(pdf, 'ThumbnailingImageReader', FailingImageReader)
    canvas = CanvasSpy()

    Renderer.__new__(Renderer)._draw_poweredby(
        canvas,
        None,
        {'content': 'dark', 'size': '10', 'left': '0', 'bottom': '0'},
    )

    assert canvas.draw_calls == []


def test_draw_poweredby_draws_resized_image(monkeypatch):
    monkeypatch.setattr(pdf.finders, 'find', lambda path: 'powered-by.png')
    monkeypatch.setattr(pdf, 'ThumbnailingImageReader', ResizingImageReader)
    canvas = CanvasSpy()

    Renderer.__new__(Renderer)._draw_poweredby(
        canvas,
        None,
        {'content': 'dark', 'size': '10', 'left': '0', 'bottom': '0'},
    )

    assert len(canvas.draw_calls) == 1
    args, kwargs = canvas.draw_calls[0]
    assert isinstance(args[0], ResizingImageReader)
    assert kwargs['width'] == 12
    assert kwargs['height'] == 34
