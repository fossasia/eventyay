from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, Organizer, Team, User
from eventyay.base.models.organizer import TeamAPIToken


def create_core_team(organizer: Organizer, user: User) -> Team:
    t = Team.objects.create(
        organizer=organizer,
        name=_('Core Organizing Team'),
        is_core_team=True,
        all_events=True,
        can_create_events=True,
        can_change_teams=True,
        can_manage_gift_cards=True,
        can_change_organizer_settings=True,
        can_change_event_settings=True,
        can_change_config=True,
        can_change_items=True,
        can_view_orders=True,
        can_change_orders=True,
        can_manage_bank_transfers=True,
        can_checkin_orders=True,
        can_view_vouchers=True,
        can_change_vouchers=True,
        can_change_submissions=True,
        is_reviewer=True,
        can_change_exhibition_proposals=True,
        is_exhibition_reviewer=True,
        can_manage_social_media=True,
        can_video_manage_content=True,
        can_video_moderate=True,
        can_video_manage_kiosks=True,
        can_video_view_analytics=True,
    )
    t.members.add(user)
    return t


def is_event_core_team_member(user: User, event: Event) -> bool:
    """
    Whether ``user`` belongs to a Core Organizing Team of the event's organizer that covers ``event``.

    This is deliberately a membership check, not a team permission: API tokens and devices of the core
    team do not pass it, and no team setting editable by organizers can grant it. Who may add or remove
    members of a core team is restricted by ``can_manage_team_members()``.
    """
    if not user.is_authenticated or not user.is_active:
        return False
    return (
        Team.objects.filter(organizer_id=event.organizer_id, is_core_team=True, members=user)
        .filter(Q(all_events=True) | Q(limit_events=event))
        .exists()
    )


CORE_TEAM_MEMBERS_DENIED = _(
    'Only members of the Core Organizing Team can add, invite or remove its members, '
    'resend or revoke its invitations, and create or revoke its API tokens.'
)
CORE_TEAM_LAST_MEMBER = _('You cannot remove the last active member of the Core Organizing Team.')


def can_manage_team_members(
    team: Team,
    *,
    user: User | None = None,
    session_key: str | None = None,
    token: TeamAPIToken | None = None,
) -> bool:
    """
    Whether the actor may add, invite or remove members of ``team``, resend and revoke its invitations, or
    create and revoke its API tokens.

    Any team manager may do this for an ordinary team. For a core team it is limited to members of the
    organizer's core team, to the API tokens of that team, and to platform administrators with an active
    staff session. Otherwise a manager could invite themselves into the core team and pass
    ``is_event_core_team_member()``, or create a token of the core team and use it to do the same.
    """
    if not team.is_core_team:
        return True
    if user is not None and user.is_authenticated:
        if user.has_active_staff_session(session_key):
            return True
        return (
            user.is_active
            and Team.objects.filter(organizer_id=team.organizer_id, is_core_team=True, members=user).exists()
        )
    if token is not None:
        return token.active and token.team.is_core_team and token.team.organizer_id == team.organizer_id
    return False


def removes_last_active_core_member(team: Team, user: User) -> bool:
    """Whether removing ``user`` would leave the core team without an active member."""
    return team.is_core_team and not team.members.exclude(pk=user.pk).filter(is_active=True).exists()
