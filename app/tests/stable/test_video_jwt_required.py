import pytest
import jwt

from eventyay.base.services.user import AuthError, login
from eventyay.core.permissions import Permission
from eventyay.eventyay_common.video.permissions import video_attendee_trait


@pytest.mark.django_db
def test_anonymous_client_id_denied_without_jwt(event):
    assert event.settings.get('venueless_show_public_link', False) is False
    with pytest.raises(AuthError) as exc:
        login(event=event, client_id='anonymous-client')
    assert exc.value.code == 'auth.missing_token'


@pytest.mark.django_db
def test_attendee_jwt_trait_grants_access(event):
    assert event.has_permission_implicit(
        traits=['attendee', video_attendee_trait(event.slug)],
        permissions=[Permission.EVENT_VIEW],
        allow_empty_traits=False,
    )


@pytest.mark.django_db
def test_public_video_link_allows_anonymous_access(event):
    event.settings.set('venueless_show_public_link', True)
    result = login(event=event, client_id='public-anonymous-client')
    assert result.user.client_id == 'public-anonymous-client'


@pytest.mark.django_db
def test_decode_token_without_config_raises_invalid_token(event):
    event.config = None
    event.save(update_fields=['config'])
    with pytest.raises(jwt.exceptions.InvalidTokenError):
        event.decode_token('not-a-jwt', allow_raise=True)
