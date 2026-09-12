from unittest.mock import MagicMock, patch

from django.test import override_settings

from eventyay.base.models.auth import User
from eventyay.eventyay_common.views.organizer import OrganizerTeamsView
from eventyay.eventyay_common.views.team import TeamMemberView


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    },
)
def test_organizer_teams_view_removes_member_when_in_team():
    """Verify legitimate team member removal succeeds and logs action."""
    view = OrganizerTeamsView()
    view.request = MagicMock()
    view.request.user = MagicMock(pk=1)
    view.request.organizer = MagicMock()
    view._redirect_to_team_permissions = MagicMock(return_value='redirect_permissions')

    team = MagicMock(pk=10, can_change_teams=False)
    member = MagicMock(pk=99, email='member@example.com')
    team.members.get.return_value = member
    team.members.count.return_value = 2

    with patch('eventyay.eventyay_common.views.organizer.sync_video_traits_for_team') as mock_sync:
        result = view._handle_remove_member(team, {'remove-member': '99'})

        team.members.get.assert_called_once_with(pk='99')
        team.members.remove.assert_called_once_with(member)
        team.log_action.assert_called_once_with(
            'eventyay.team.member.removed',
            user=view.request.user,
            data={'email': 'member@example.com', 'user': 99},
        )
        mock_sync.assert_called_once_with(team, members=[member])
        assert result == 'redirect_permissions'


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    },
)
def test_organizer_teams_view_rejects_non_member_and_prevents_pii_leak():
    """Verify removing a non-member does not log action, leak PII, or sync traits."""
    view = OrganizerTeamsView()
    view.request = MagicMock()
    view.request.user = MagicMock(pk=1)
    view._redirect_to_team_permissions = MagicMock(return_value='redirect_permissions')

    team = MagicMock(pk=10)
    team.members.get.side_effect = User.DoesNotExist

    with patch('eventyay.eventyay_common.views.organizer.sync_video_traits_for_team') as mock_sync:
        result = view._handle_remove_member(team, {'remove-member': '999'})

        team.members.get.assert_called_once_with(pk='999')
        team.members.remove.assert_not_called()
        team.log_action.assert_not_called()
        mock_sync.assert_not_called()
        assert result == 'redirect_permissions'


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    },
)
def test_legacy_team_member_view_rejects_non_member():
    """Verify legacy TeamMemberView also scopes user lookup to team membership."""
    view = TeamMemberView()
    view.request = MagicMock()
    view.request.POST = {'remove-member': '999'}
    view.get_object = MagicMock()
    view.get_success_url = MagicMock(return_value='/success/')

    team = MagicMock(pk=10)
    team.members.get.side_effect = User.DoesNotExist
    view.get_object.return_value = team

    with (
        patch('eventyay.eventyay_common.views.team.sync_video_traits_for_team') as mock_sync,
        patch('eventyay.eventyay_common.views.team.redirect') as mock_redirect,
    ):
        mock_redirect.return_value = 'redirected'
        post_func = getattr(view.post, '__wrapped__', view.post)
        result = post_func(view, view.request)

        team.members.get.assert_called_once_with(pk='999')
        team.members.remove.assert_not_called()
        team.log_action.assert_not_called()
        mock_sync.assert_not_called()
        assert result == 'redirected'
