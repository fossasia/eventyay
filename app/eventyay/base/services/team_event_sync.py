"""
Sync events to Talk-only teams so they appear in dashboards.

Talk-only teams have Talk permissions (e.g. can_change_submissions or is_reviewer)
but no ticket or settings permissions. They get all organizer events in limit_events
so events show up in the general dashboard.
"""

import logging

from django_scopes import scopes_disabled

logger = logging.getLogger(__name__)


def is_talk_only_permission_mapping(mapping):
    """
    Return True if permission flags describe a Talk-only team: Talk permissions
    present, and no ticket or organizer/event settings permissions.

    ``mapping`` is any object supporting ``.get()`` with the same keys as Team
    permission fields (e.g. cleaned form data or a dict).
    """
    has_talk_perms = bool(
        mapping.get("can_change_submissions") or mapping.get("is_reviewer")
    )
    has_ticket_perms = bool(
        mapping.get("can_view_orders")
        or mapping.get("can_change_orders")
        or mapping.get("can_change_items")
        or mapping.get("can_view_vouchers")
        or mapping.get("can_change_vouchers")
        or mapping.get("can_checkin_orders")
    )
    has_settings_perms = bool(
        mapping.get("can_change_event_settings")
        or mapping.get("can_change_organizer_settings")
    )
    return has_talk_perms and not has_ticket_perms and not has_settings_perms


def is_talk_only_team(team):
    """
    Return True if this team is Talk-only: has Talk permissions but no
    ticket or settings permissions (same logic as control team form validation).
    """
    return is_talk_only_permission_mapping(
        {
            "can_change_submissions": getattr(team, "can_change_submissions", False),
            "is_reviewer": getattr(team, "is_reviewer", False),
            "can_view_orders": getattr(team, "can_view_orders", False),
            "can_change_orders": getattr(team, "can_change_orders", False),
            "can_change_items": getattr(team, "can_change_items", False),
            "can_view_vouchers": getattr(team, "can_view_vouchers", False),
            "can_change_vouchers": getattr(team, "can_change_vouchers", False),
            "can_checkin_orders": getattr(team, "can_checkin_orders", False),
            "can_change_event_settings": getattr(
                team, "can_change_event_settings", False
            ),
            "can_change_organizer_settings": getattr(
                team, "can_change_organizer_settings", False
            ),
        }
    )


def sync_events_to_talk_only_team(team, events=None):
    """
    Add events to a Talk-only team's limit_events so they appear in the dashboard.

    :param team: Team instance (should be Talk-only and not all_events).
    :param events: Optional list of Event instances to add. If None, add all
        organizer events.
    """
    if not team.pk or team.all_events:
        return
    if not is_talk_only_team(team):
        logger.warning(
            "sync_events_to_talk_only_team called with non Talk-only team id=%s",
            team.pk,
        )
        return
    with scopes_disabled():
        if events is None:
            events = list(team.organizer.events.all())
        if not events:
            return
        events = [
            e
            for e in events
            if e.pk and e.organizer_id == team.organizer_id
        ]
        if not events:
            return
        existing = set(team.limit_events.values_list("pk", flat=True))
        to_add = [e for e in events if e.pk not in existing]
        if to_add:
            team.limit_events.add(*to_add)
            logger.info(
                "Added %s event(s) to Talk-only team id=%s limit_events",
                len(to_add),
                team.pk,
            )


def sync_all_talk_only_teams():
    """
    Sync events to all Talk-only teams (all_events=False) that qualify.
    Used at startup and after migrations.

    :return: Dict with keys teams_processed, teams_synced, events_added.
    """
    from eventyay.base.models.organizer import Team

    teams_processed = 0
    teams_synced = 0
    events_added = 0

    with scopes_disabled():
        for team in Team.objects.filter(all_events=False).select_related("organizer"):
            teams_processed += 1
            if not is_talk_only_team(team):
                continue
            before = team.limit_events.count()
            sync_events_to_talk_only_team(team)
            after = team.limit_events.count()
            if after > before:
                teams_synced += 1
                events_added += after - before

    return {
        "teams_processed": teams_processed,
        "teams_synced": teams_synced,
        "events_added": events_added,
    }
