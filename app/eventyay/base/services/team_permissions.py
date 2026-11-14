"""Effective access that can be delegated through an organizer team."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from copy import copy
from dataclasses import dataclass
from typing import cast

from django.db.models import Prefetch
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.models import Event, Organizer
from eventyay.base.models.auth import StaffSession, User
from eventyay.base.models.organizer import Team, TeamAPIToken
from eventyay.base.models.track import Track


TEAM_DELEGATION_ERROR = _('You can only grant permissions and event access that you already have.')
# Team management also gates token actions on individual events.
ORGANIZER_ONLY_PERMISSIONS = frozenset({'can_create_events', 'can_change_organizer_settings', 'can_manage_gift_cards'})
TALK_PERMISSIONS = frozenset({'is_reviewer', 'can_change_submissions'})
EXHIBITION_PERMISSIONS = frozenset({'is_exhibition_reviewer', 'can_change_exhibition_proposals'})
GRANT_FIELDS = (
    'all_events',
    'force_hide_speaker_names',
    'force_hide_speaker_emails',
    'hide_exhibition_applicant_emails',
    'teamshifts_role',
    'all_teamshifts_roles',
    'limit_teamshifts_roles',
    'hide_teamshifts_emails',
)

# None denotes access to all current and future tracks or TeamShifts roles.
type GrantScope = frozenset[int] | None
type Grants = dict[tuple[str, str], GrantScope]


def lock_team_organizer(organizer_id: int) -> None:
    """Serialize delegation writes before locking any target or source team."""
    Organizer.objects.select_for_update(no_key=True).values_list('pk', flat=True).get(pk=organizer_id)


@dataclass
class TeamGrant:
    team: Team
    events: GrantScope
    tracks: dict[int, frozenset[int]] | None

    @classmethod
    def from_team(cls, team: Team, changes: Mapping[str, object]) -> 'TeamGrant':
        proposed = copy(team) if changes else team
        for field in (*Team._permission_field_names(), *GRANT_FIELDS):
            if field in changes:
                setattr(proposed, field, changes[field])

        events = None
        if not proposed.all_events:
            selected = (
                cast(Iterable[Event], changes['limit_events'])
                if 'limit_events' in changes
                else (team.limit_events.all() if team.pk else ())
            )
            events = frozenset(event.pk for event in selected)

        tracks = None
        if proposed.permission_set() & TALK_PERMISSIONS:
            selected_tracks = (
                cast(Iterable[Track], changes['limit_tracks'])
                if 'limit_tracks' in changes
                else (team.limit_tracks.all() if team.pk else ())
            )
            track_ids = defaultdict(set)
            for track in selected_tracks:
                track_ids[track.event_id].add(track.pk)
            if track_ids:
                tracks = {event_id: frozenset(ids) for event_id, ids in track_ids.items()}

        return cls(proposed, events, tracks)

    def covers_event(self, event_id: int | None) -> bool:
        return self.events is None or event_id in self.events

    @cached_property
    def permissions(self) -> set[str]:
        return self.team.permission_set()

    def grants_for_event(self, event_id: int | None) -> Grants:
        if not self.covers_event(event_id):
            return {}

        grants = {}
        for permission in self.permissions - ORGANIZER_ONLY_PERMISSIONS:
            grants[permission, 'access'] = None
            if permission in TALK_PERMISSIONS:
                tracks = None if self.tracks is None else self.tracks.get(event_id, frozenset())
                grants[permission, 'tracks'] = tracks
                if not self.team.force_hide_speaker_names:
                    grants[permission, 'speaker_names'] = tracks
                    if not self.team.force_hide_speaker_emails:
                        grants[permission, 'speaker_emails'] = tracks
            elif permission in EXHIBITION_PERMISSIONS and not self.team.hide_exhibition_applicant_emails:
                grants[permission, 'applicant_emails'] = None

        if self.team.can_change_event_settings or self.team.teamshifts_role == 'coordinator':
            grants.update(
                {('teamshifts', capability): None for capability in ('coordinator', 'lead', 'roles', 'emails')}
            )
        elif self.team.teamshifts_role == 'lead':
            roles = None if self.team.all_teamshifts_roles else frozenset(self.team.limit_teamshifts_roles or ())
            grants['teamshifts', 'lead'] = None
            grants['teamshifts', 'roles'] = roles
            if not self.team.hide_teamshifts_emails:
                grants['teamshifts', 'emails'] = roles
        return grants


def added_grants(previous: Grants, proposed: Grants) -> Grants:
    added = {}
    for key, requested in proposed.items():
        existing = previous.get(key, frozenset())
        if existing is None:
            continue
        if requested is None:
            added[key] = None
        elif requested - existing:
            added[key] = requested - existing
    return added


class TeamDelegation:
    def __init__(
        self, organizer: Organizer, actor: User | TeamAPIToken, *, session_key: str | None = None, lock: bool = False
    ):
        self.organizer = organizer
        self.actor = actor
        self.session_key = session_key
        self.lock = lock

    @cached_property
    def staff_override(self) -> bool:
        active = (
            isinstance(self.actor, User)
            and bool(self.session_key)
            and self.actor.has_active_staff_session(self.session_key)
        )
        if active and self.lock:
            return (
                StaffSession.objects.select_for_update(no_key=True)
                .filter(user=self.actor, user__is_staff=True, session_key=self.session_key, date_end__isnull=True)
                .exists()
            )
        return active

    @cached_property
    def event_ids(self) -> frozenset[int]:
        return frozenset(self.organizer.events.values_list('pk', flat=True))

    @cached_property
    def sources(self) -> tuple[TeamGrant, ...]:
        teams = self.organizer.teams.all()
        if isinstance(self.actor, TeamAPIToken):
            teams = teams.filter(pk=self.actor.team_id, tokens__pk=self.actor.pk, tokens__active=True)
        elif isinstance(self.actor, User) and self.actor.is_authenticated:
            teams = teams.filter(members=self.actor)
        else:
            return ()
        if self.lock:
            # The join locks the actual membership or token row as well as its team.
            teams = teams.order_by('pk').select_for_update(no_key=True)
        with scope(event=tuple(self.event_ids)):
            return tuple(
                TeamGrant.from_team(team, {})
                for team in teams.prefetch_related(
                    Prefetch('limit_events', queryset=self.organizer.events.all()), 'limit_tracks'
                )
            )

    @cached_property
    def organizer_grants(self) -> set[str]:
        return {permission for source in self.sources for permission in source.permissions}

    def available_for_event(self, event_id: int | None) -> Grants:
        available = {}
        for source in self.sources:
            for key, granted in source.grants_for_event(event_id).items():
                existing = available.get(key, frozenset())
                available[key] = None if granted is None or existing is None else existing | granted
        return available

    def allows(self, *, team: Team | None = None, changes: Mapping[str, object] | None = None) -> bool:
        """Check the full access delegated by an invite or token, or the access added by an edit."""
        if not isinstance(self.actor, (User, TeamAPIToken)):
            return False
        if self.staff_override:
            return True

        with scope(event=tuple(self.event_ids)):
            previous = TeamGrant.from_team(team, {}) if team is not None and changes is not None else None
            proposed = TeamGrant.from_team(team if team is not None else Team(), changes or {})

        if proposed.events is not None and proposed.events - self.event_ids:
            return False
        before = previous.permissions if previous is not None else set()
        new_permissions = proposed.permissions - before
        if new_permissions and new_permissions - self.organizer_grants:
            return False

        # The future-event check prevents a grant based only on access to today's events.
        event_ids = (*self.event_ids, None) if proposed.events is None else proposed.events
        for event_id in event_ids:
            existing = previous.grants_for_event(event_id) if previous is not None else {}
            required = added_grants(existing, proposed.grants_for_event(event_id))
            if required and added_grants(self.available_for_event(event_id), required):
                return False
        return True


def can_delegate_team_permissions(
    organizer: Organizer,
    actor: User | TeamAPIToken,
    *,
    session_key: str | None = None,
    team: Team | None = None,
    changes: Mapping[str, object] | None = None,
    lock: bool = False,
) -> bool:
    return TeamDelegation(organizer, actor, session_key=session_key, lock=lock).allows(team=team, changes=changes)
