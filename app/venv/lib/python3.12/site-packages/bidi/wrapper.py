"""Provides a wrpper for the Rust based implementation."""

from typing import Optional, Union

from .bidi import get_base_level_inner, get_display_inner

StrOrBytes = Union[str, bytes]

def get_display(
    str_or_bytes: StrOrBytes,
    encoding: str = "utf-8",
    base_dir: Optional[str] = None,
    debug: bool = False,
) -> StrOrBytes:
    """Accepts string or bytes. In case of bytes, `encoding`
    is needed as the inner function expects a valid string (default:"utf-8").

    Set `base_dir` to 'L' or 'R' to override the calculated base_level.

    Set `debug` to True to return the calculated levels.

    Returns the display layout, either as unicode or `encoding` encoded
    string.

    """
    if isinstance(str_or_bytes, bytes):
        text = str_or_bytes.decode(encoding)
        was_decoded = True
    else:
        text = str_or_bytes
        was_decoded = False

    display = get_display_inner(text, base_dir, debug)

    if was_decoded:
        display = display.encode(encoding)

    return display


def get_base_level(text: str) -> int:
    """Returns the base unicode level of the 1st paragraph in `text`.

    Return value of 0 means LTR, while 1 means RTL.
    """
    return get_base_level_inner(text)
