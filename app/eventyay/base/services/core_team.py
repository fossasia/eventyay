from django_scopes import scopes_disabled

from eventyay.base.models import Team


def is_event_core_team_member(user, event) -> bool:
    """Whether ``user`` belongs to the core organizing team of the event's organizer.

    The core organizing team is flagged by platform administrators and is the only team that may
    anonymize ticketing data, so the check is deliberately independent of regular team permissions.
    """
    if user is None or event is None or not getattr(user, 'is_authenticated', False):
        return False
    with scopes_disabled():
        return Team.objects.filter(
            organizer_id=event.organizer_id,
            is_core_team=True,
            members__pk=user.pk,
        ).exists()
