from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Team


def create_core_team(organizer, user):
    t = Team.objects.create(
        organizer=organizer,
        name=_('Core Organizing Team'),
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
