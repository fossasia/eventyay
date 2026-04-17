from contextlib import contextmanager
from unittest.mock import patch


class _Mocker:
    def __init__(self):
        self._patchers = []

    def patch(self, target, *args, **kwargs):
        p = patch(target, *args, **kwargs)
        mocked = p.start()
        self._patchers.append(p)
        return mocked

    def stopall(self):
        while self._patchers:
            self._patchers.pop().stop()


@contextmanager
def mocker_context():
    mocker = _Mocker()
    try:
        yield mocker
    finally:
        mocker.stopall()
