from rest_framework import exceptions
from rest_framework.request import Request

from eventyay.base.models import Team
from eventyay.base.models.organizer import TeamAPIToken
from eventyay.base.services.organizer_creation import CORE_TEAM_MEMBERS_DENIED, can_manage_team_members


def ensure_can_manage_team_members(request: Request, team: Team) -> None:
    """Refuse changes to the members and invitations of a core team to anyone but its own side."""
    token = request.auth if isinstance(request.auth, TeamAPIToken) else None
    if not can_manage_team_members(team, user=request.user, session_key=request.session.session_key, token=token):
        raise exceptions.PermissionDenied(CORE_TEAM_MEMBERS_DENIED)
