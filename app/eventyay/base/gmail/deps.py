from django.utils.translation import gettext_lazy as _


def require_google_api_dependencies():
    """
    Import Google API client libraries on demand.

    Keeps Django startup working when the optional Gmail dependencies are not
    installed yet (for example in an older Docker image). Gmail features raise a
    clear error until `uv sync --all-extras --all-groups` has been run.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ModuleNotFoundError as exc:
        raise ImportError(
            _(
                'Gmail support requires the Google API client libraries. '
                'Rebuild the application image or run `uv sync --all-extras --all-groups`.'
            )
        ) from exc
    return Request, Credentials, build, HttpError
