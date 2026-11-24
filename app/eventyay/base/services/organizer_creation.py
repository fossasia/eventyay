from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, Organizer, Team, User


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
    team do not pass it, and no team setting editable by organizers can grant it.
    """
    if not user.is_authenticated or not user.is_active:
        return False
    return (
        Team.objects.filter(organizer_id=event.organizer_id, is_core_team=True, members=user)
        .filter(Q(all_events=True) | Q(limit_events=event))
        .exists()
    )
