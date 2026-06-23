import rules


@rules.predicate
def can_view_speaker_names(user, obj):
    """ONLY in use with users who don't have change permissions."""
    event = obj.event
    reviewer_teams = obj.event.teams.filter(members__in=[user], is_reviewer=True)
    if reviewer_teams and all(team.force_hide_speaker_names for team in reviewer_teams):
        return False
    return bool(event.active_review_phase and event.active_review_phase.can_see_speaker_names)


@rules.predicate
def can_view_speaker_emails(user, obj):
    """ONLY in use with users who don't have change permissions."""
    event = obj.event
    reviewer_teams = obj.event.teams.filter(members__in=[user], is_reviewer=True)
    if reviewer_teams and any(team.force_hide_speaker_emails for team in reviewer_teams):
        return False
    return can_view_speaker_names(user, obj)


@rules.predicate
def enforces_hide_speaker_emails(user, obj):
    event = getattr(obj, 'event', obj)
    user_teams = event.teams.filter(members__in=[user])
    return bool(user_teams and any(team.force_hide_speaker_emails for team in user_teams))


@rules.predicate
def enforces_hide_speaker_names(user, obj):
    event = getattr(obj, 'event', obj)
    user_teams = event.teams.filter(members__in=[user])
    return bool(user_teams and any(team.force_hide_speaker_names for team in user_teams))
