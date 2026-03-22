"""
Tests for syncing new events to Talk-only teams' ``limit_events`` on event creation.
"""

import datetime

import pytest
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer, Team


@pytest.mark.django_db
def test_new_event_added_to_talk_only_team_limit_events():
    """Talk-only teams (limited, Talk perms only) receive the new event in ``limit_events``."""
    with scopes_disabled():
        org = Organizer.objects.create(name='Org', slug='org-sync-t1')
        existing = Event.objects.create(
            organizer=org,
            name='Existing',
            slug='existing-t1',
            date_from=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),
        )
        talk_team = Team.objects.create(
            organizer=org,
            name='Talk only',
            all_events=False,
            can_change_submissions=True,
        )
        # Team.save syncs Talk-only teams to existing organizer events; creation of
        # ``new_event`` must still add that event via ``Event._sync_to_talk_only_teams``.
        assert talk_team.limit_events.filter(pk=existing.pk).exists()

        new_event = Event.objects.create(
            organizer=org,
            name='New',
            slug='new-t1',
            date_from=datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc),
        )

        talk_team.refresh_from_db()
        assert talk_team.limit_events.filter(pk=new_event.pk).exists()
        assert set(talk_team.limit_events.values_list('pk', flat=True)) == {existing.pk, new_event.pk}


@pytest.mark.django_db
def test_new_event_does_not_modify_non_talk_only_limited_team():
    """Limited teams that are not Talk-only (e.g. have ticket perms) are unchanged by the hook."""
    with scopes_disabled():
        org = Organizer.objects.create(name='Org', slug='org-sync-t2')
        existing = Event.objects.create(
            organizer=org,
            name='Existing',
            slug='existing-t2',
            date_from=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),
        )
        ticket_team = Team.objects.create(
            organizer=org,
            name='Ticket limited',
            all_events=False,
            can_view_orders=True,
            can_change_orders=True,
        )
        ticket_team.limit_events.add(existing)

        new_event = Event.objects.create(
            organizer=org,
            name='New',
            slug='new-t2',
            date_from=datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc),
        )

        ticket_team.refresh_from_db()
        assert set(ticket_team.limit_events.values_list('pk', flat=True)) == {existing.pk}
        assert not ticket_team.limit_events.filter(pk=new_event.pk).exists()
