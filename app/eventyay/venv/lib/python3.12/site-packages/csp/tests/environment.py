from typing import Any

from jinja2 import Environment


def environment(**options: Any) -> Environment:
    env = Environment(**options)
    return env
