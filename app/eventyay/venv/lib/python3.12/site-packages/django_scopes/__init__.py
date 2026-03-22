from .exceptions import ScopeError
from .manager import ScopedManager
from .state import get_scope, scope, scopes_disabled

version = '2.0.0'

__all__ = [
    'version',
    'ScopeError',
    'ScopedManager',
    'scope',
    'get_scope',
    'scopes_disabled'
]
