from typing import Any

from django_markup.filter import MarkupFilter


class TextileMarkupFilter(MarkupFilter):
    title = "Textile"

    def render(
        self,
        text: str,
        **kwargs: Any,  # Unused argument
    ) -> str:
        from textile import textile  # noqa: PLC0415

        return textile(text, **kwargs)
