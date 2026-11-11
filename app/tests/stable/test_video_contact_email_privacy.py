import pytest
from django_scopes import scopes_disabled

from eventyay.base.models.auth import User
from eventyay.base.services.user import get_public_users, list_users, update_user

fetch_users = getattr(get_public_users, 'func', get_public_users)
search_users = getattr(list_users, 'func', list_users)


def make_video_user(event, name, email):
    return User.objects.create(
        event=event,
        token_id=f'token-{name}',
        show_publicly=True,
        profile={'display_name': name, 'contact_email': email},
    )


@pytest.mark.django_db
def test_contact_email_not_in_public_serialization(event):
    with scopes_disabled():
        alice = make_video_user(event, 'alice', 'alice@example.invalid')
        make_video_user(event, 'bob', 'bob@example.invalid')

        assert 'contact_email' not in alice.serialize_public()['profile']

        fetched = fetch_users(event.id, ids=[str(alice.id)])
        assert fetched[0]['profile'] == {'display_name': 'alice'}

        listed = search_users(event_id=event.id, page=1, page_size=20, search_term='')
        assert all('contact_email' not in u['profile'] for u in listed['results'])


@pytest.mark.django_db
def test_admin_still_sees_contact_email(event):
    with scopes_disabled():
        alice = make_video_user(event, 'alice', 'alice@example.invalid')
        fetched = fetch_users(event.id, ids=[str(alice.id)], include_admin_info=True)
        assert fetched[0]['email'] == 'alice@example.invalid'
        assert 'contact_email' not in fetched[0]['profile']


@pytest.mark.django_db
def test_profile_update_cannot_change_or_drop_contact_email(event):
    with scopes_disabled():
        alice = make_video_user(event, 'alice', 'alice@example.invalid')

        update_user(
            event.id,
            alice.id,
            data={'profile': {'display_name': 'Alice', 'contact_email': 'evil@example.invalid'}},
            serialize=False,
        )
        alice.refresh_from_db()
        assert alice.profile == {'display_name': 'Alice', 'contact_email': 'alice@example.invalid'}

        update_user(event.id, alice.id, data={'profile': {'display_name': 'Alice A.'}}, serialize=False)
        alice.refresh_from_db()
        assert alice.profile['contact_email'] == 'alice@example.invalid'
