import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils.timezone import now
from rest_framework.exceptions import AuthenticationFailed

from eventyay.api.auth.token import TeamTokenAuthentication
from eventyay.base.models.auth_token import UserApiToken, generate_api_token
from eventyay.base.models.organizer import TeamAPIToken
from eventyay.common.auth import UserOrTeamTokenAuthentication


@pytest.mark.django_db
def test_user_or_team_token_accepts_user_api_token(orga_user, event):
    token_value = generate_api_token()
    token = UserApiToken.objects.create(
        name='user-token',
        user=orga_user,
        token=token_value,
    )
    token.events.set([event])

    user, auth = UserOrTeamTokenAuthentication().authenticate_credentials(token_value)
    assert user == orga_user
    assert auth == token
    assert isinstance(auth, UserApiToken)


@pytest.mark.django_db
def test_user_or_team_token_matches_legacy_team_token_auth(orga_user, event):
    """Team tokens must keep the same (AnonymousUser, TeamAPIToken) return shape."""
    team = event.organizer.teams.filter(members=orga_user).first()
    assert team is not None
    token_value = generate_api_token()
    token = TeamAPIToken.objects.create(
        name='team-token',
        team=team,
        token=token_value,
    )

    combined = UserOrTeamTokenAuthentication().authenticate_credentials(token_value)
    legacy = TeamTokenAuthentication().authenticate_credentials(token_value)

    assert isinstance(combined[0], AnonymousUser)
    assert combined[1] == token
    assert type(combined[0]) is type(legacy[0])
    assert combined[1] == legacy[1]


@pytest.mark.django_db
def test_user_or_team_token_rejects_inactive_team_token(orga_user, event):
    team = event.organizer.teams.filter(members=orga_user).first()
    token_value = generate_api_token()
    TeamAPIToken.objects.create(
        name='inactive-team-token',
        team=team,
        token=token_value,
        active=False,
    )

    with pytest.raises(AuthenticationFailed, match='inactive'):
        UserOrTeamTokenAuthentication().authenticate_credentials(token_value)


@pytest.mark.django_db
def test_user_or_team_token_rejects_expired_user_token(orga_user, event):
    token_value = generate_api_token()
    token = UserApiToken.objects.create(
        name='expired-user-token',
        user=orga_user,
        token=token_value,
        expires=now(),
    )
    token.events.set([event])

    with pytest.raises(AuthenticationFailed, match='Invalid token'):
        UserOrTeamTokenAuthentication().authenticate_credentials(token_value)


@pytest.mark.django_db
def test_user_or_team_token_rejects_unknown_token():
    with pytest.raises(AuthenticationFailed, match='Invalid token'):
        UserOrTeamTokenAuthentication().authenticate_credentials('not-a-real-token')


@pytest.mark.django_db
def test_user_or_team_token_ignores_non_token_authorization(rf):
    """Device/OAuth/session headers must not be claimed by this authenticator."""
    request = rf.get('/')
    request.META['HTTP_AUTHORIZATION'] = f'Device {generate_api_token()}'
    assert UserOrTeamTokenAuthentication().authenticate(request) is None
