import pytest
from django_scopes import scopes_disabled

from eventyay.base.models.auth import User, public_profile
from eventyay.base.services.user import get_public_users, list_users, update_user
from eventyay.features.live.exceptions import ConsumerException

fetch_users = getattr(get_public_users, 'func', get_public_users)
search_users = getattr(list_users, 'func', list_users)


def make_video_user(event, name, email):
    """Create an event-scoped video user whose profile carries a ticket contact email."""
    return User.objects.create(
        event=event,
        token_id=f'token-{name}',
        show_publicly=True,
        profile={'display_name': name, 'contact_email': email},
    )


@pytest.mark.django_db
def test_contact_email_not_in_public_serialization(event):
    """Public serializers must not expose contact_email."""
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
    """Admin info exposes contact_email via the email field, not the profile."""
    with scopes_disabled():
        alice = make_video_user(event, 'alice', ' alice@example.invalid ')
        serialized = alice.serialize_public(include_admin_info=True)
        assert serialized['email'] == 'alice@example.invalid'
        assert 'contact_email' not in serialized['profile']

        alice.profile = {'display_name': 'alice', 'contact_email': 'alice@example.invalid'}
        alice.save(update_fields=['profile'])
        fetched = fetch_users(event.id, ids=[str(alice.id)], include_admin_info=True)
        assert fetched[0]['email'] == 'alice@example.invalid'
        assert 'contact_email' not in fetched[0]['profile']


@pytest.mark.django_db
def test_profile_update_cannot_change_or_drop_contact_email(event):
    """Clients cannot overwrite or remove the server-set contact_email."""
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


@pytest.mark.django_db
def test_profile_update_rejects_non_object(event):
    """A non-dict profile is rejected and the stored profile is kept."""
    with scopes_disabled():
        alice = make_video_user(event, 'alice', 'alice@example.invalid')
        with pytest.raises(ConsumerException):
            update_user(event.id, alice.id, data={'profile': 'not-an-object'}, serialize=False)
        alice.refresh_from_db()
        assert alice.profile['contact_email'] == 'alice@example.invalid'


def test_public_profile_keeps_non_object_values():
    """Legacy non-dict profiles are passed through instead of raising."""
    assert public_profile(None) is None
    assert public_profile(['legacy']) == ['legacy']
    assert public_profile({'display_name': 'a', 'contact_email': 'x'}) == {'display_name': 'a'}
