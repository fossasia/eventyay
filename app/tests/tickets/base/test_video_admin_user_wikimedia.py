import pytest

from eventyay.base.models import User
from eventyay.base.services.user import (
    admin_public_fields_with_email_fallback,
    resolve_wikimedia_usernames_by_email,
)


@pytest.mark.django_db
def test_admin_wikimedia_username_falls_back_to_account_email():
    User.objects.create(
        email="wiki-fallback@example.org",
        wikimedia_username="WikiUser42",
    )

    user_row = {
        "token_id": "ABC1234",
        "moderation_state": "",
        "email": "",
        "profile": {},
        "wikimedia_username": "",
    }
    ticket_by_token = {
        "ABC1234": {
            "contact_email": "wiki-fallback@example.org",
            "order_code": "ORD123",
            "ticket_code": "TCK123",
        }
    }

    email_to_wikimedia = resolve_wikimedia_usernames_by_email(
        ["wiki-fallback@example.org"]
    )
    data = admin_public_fields_with_email_fallback(
        user_row, ticket_by_token, email_to_wikimedia
    )

    assert data["email"] == "wiki-fallback@example.org"
    assert data["wikimedia_username"] == "WikiUser42"
