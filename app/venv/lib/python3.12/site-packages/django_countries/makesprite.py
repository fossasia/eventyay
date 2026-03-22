#!/usr/bin/env python
"""
Builds all flags into a single sprite image (along with some css).
"""

import os
import re
from typing import IO

from PIL import Image

re_flag_file = re.compile(r"[a-z]{2}.gif$")
FLAG_X, FLAG_Y = 16, 11


def main() -> None:
    flag_path = os.path.join(os.path.dirname(__file__), "static", "flags")
    files = os.listdir(flag_path)
    img = Image.new("RGBA", (26 * FLAG_X, 26 * FLAG_Y))
    for name in files:
        if not re_flag_file.match(name):
            continue
        x = (ord(name[0]) - 97) * FLAG_X
        y = (ord(name[1]) - 97) * FLAG_Y
        flag_img = Image.open(os.path.join(flag_path, name))
        img.paste(flag_img, (x, y))
    img.save(os.path.join(flag_path, "sprite-hq.png"))
    img = img.quantize(method=2, kmeans=1)
    img.save(os.path.join(flag_path, "sprite.png"))
    initial_css = (
        f".flag-sprite {{display: inline-block;width:{FLAG_X}px;height:{FLAG_Y}px;"
        "image-rendering:-moz-crisp-edges;image-rendering:pixelated;"
        "image-rendering:-o-crisp-edges;"
        "-ms-interpolation-mode:nearest-neighbor;"
        "background-image:url('%s')}}"
    )
    with open(os.path.join(flag_path, "sprite.css"), "w") as css_file:
        css_file.write(initial_css % "sprite.png")
        write_coords(css_file, FLAG_X, FLAG_Y)
    with open(os.path.join(flag_path, "sprite-hq.css"), "w") as css_hq_file:
        css_hq_file.write(initial_css % "sprite-hq.png")
        write_coords(css_hq_file, FLAG_X, FLAG_Y)
        for mult in range(2, 5):
            bg_size = f"{26 * FLAG_X * mult}px {26 * FLAG_Y * mult}px"
            size = f"{FLAG_X * mult}px;height:{FLAG_Y * mult}px"
            css_hq_file.write(
                f"\n.flag{mult}x {{background-size:{bg_size}}}"
                f"\n.flag{mult}x.flag-sprite {{width:{size};}}"
            )
            write_coords(
                css_hq_file, FLAG_X * mult, FLAG_Y * mult, prefix=f".flag{mult}x"
            )


def write_coords(css_file: IO[str], width: int, height: int, prefix: str = "") -> None:
    for i in range(26):
        x, y = i * width, i * height
        code = chr(i + 97)
        css_file.write(
            "\n{}.flag-{} {{background-position-x:{}}}".format(
                prefix, code, x and f"-{x}px"
            )
        )
        css_file.write(
            "\n{}.flag-_{} {{background-position-y:{}}}".format(
                prefix, code, y and f"-{y}px"
            )
        )


if __name__ == "__main__":
    main()
