"""Track-scoped access helpers for organiser teams."""

from django.db.models import Q


def applicable_talk_teams(event, user, *, reviewers_only=False):
    """Return teams that grant talk access to *user* for *event*."""
    if not user or user.is_anonymous:
        return []

    teams = event.teams.filter(members__in=[user]).prefetch_related('limit_tracks')
    if reviewers_only:
        teams = teams.filter(is_reviewer=True)
    else:
        teams = teams.filter(Q(is_reviewer=True) | Q(can_change_submissions=True))
    return [team for team in teams if team.permission_for_event(event)]


def get_allowed_tracks(event, user, *, reviewers_only=False):
    """Return track access for a user on an event.

    * ``None`` — unlimited track access for the requested scope (including
      anonymous/public consumers).
    * ``set()`` — track limits apply but none match this event (no access).
    * non-empty ``set`` — allowed :class:`~eventyay.base.models.track.Track` instances.
    """
    if not user or user.is_anonymous:
        return None
    if getattr(user, 'is_administrator', False):
        return None

    teams = applicable_talk_teams(event, user, reviewers_only=reviewers_only)
    if not teams:
        return None

    if any(not team.limit_tracks.all() for team in teams):
        return None

    from eventyay.base.models import Track

    team_pks = [team.pk for team in teams]
    return set(Track.objects.filter(event=event, team_set__pk__in=team_pks).distinct())


def user_has_track_limits(event, user, *, reviewers_only=False):
    return get_allowed_tracks(event, user, reviewers_only=reviewers_only) is not None


def apply_track_limit(queryset, event, user, *, track_field='track', reviewers_only=False):
    allowed = get_allowed_tracks(event, user, reviewers_only=reviewers_only)
    if allowed is None:
        return queryset
    if not allowed:
        return queryset.none()
    return queryset.filter(**{f'{track_field}__in': allowed})


def apply_track_limit_to_slots(queryset, event, user, *, reviewers_only=False):
    """Filter schedule slots to allowed tracks; break slots without submissions remain visible."""
    allowed = get_allowed_tracks(event, user, reviewers_only=reviewers_only)
    if allowed is None:
        return queryset
    if not allowed:
        return queryset.filter(submission__isnull=True)
    return queryset.filter(Q(submission__isnull=True) | Q(submission__track__in=allowed))


def filter_schedule_talk_data(talks, allowed_tracks):
    """Filter schedule JSON talk entries to *allowed_tracks* (a set of track PKs)."""
    if allowed_tracks is None:
        return talks
    filtered = []
    for talk in talks:
        track_id = talk.get('track')
        if track_id is None:
            # Breaks have no submission code; untracked submissions are excluded.
            if 'code' not in talk:
                filtered.append(talk)
            continue
        if track_id in allowed_tracks:
            filtered.append(talk)
    return filtered
