from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

state: ContextVar[Optional[dict]] = ContextVar('state', default=None)


@contextmanager
def scopes_disabled():
    with scope(_enabled=False):
        yield


@contextmanager
def scope(**scope_kwargs):
    previous_scope = state.get()
    if previous_scope is None:
        previous_scope = {}
        state.set(previous_scope)

    new_scope = dict(previous_scope)
    new_scope['_enabled'] = True
    new_scope.update(scope_kwargs)
    state.set(new_scope)
    try:
        yield
    finally:
        state.set(previous_scope)


def get_scope():
    return state.get() or {}
