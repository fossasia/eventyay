"""Reuse stable integration fixtures for eventyay_common tests."""

from tests.stable.conftest import (  # noqa: F401
    authenticated_client,
    event,
    organizer,
    organizer_client,
    staff_client,
    staff_user,
    team,
    user,
)
