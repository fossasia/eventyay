import pytest
from django.apps import apps
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Team
from eventyay.control.forms.organizer_forms.team_form import TeamForm


@pytest.fixture
def teamshifts_installed():
    pytest.importorskip('teamshifts')


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='Shifts Org', slug='shifts-org')


@pytest.fixture
def event(organizer):
    return Event.objects.create(
        organizer=organizer,
        name='Shifts Event',
        slug='shifts',
        date_from=now(),
        plugins='teamshifts',
    )


@pytest.mark.django_db
def test_team_form_can_remove_teamshifts_role(organizer, event, teamshifts_installed):
    with scopes_disabled():
        role = apps.get_model('teamshifts', 'TeamRole').objects.create(event=event, name='Stewards')
    team = Team.objects.create(
        organizer=organizer,
        name='Shifts Team',
        can_change_teams=True,
        teamshifts_role='lead',
        all_teamshifts_roles=False,
        limit_teamshifts_roles=[role.pk],
        hide_teamshifts_emails=True,
    )
    team.limit_events.add(event)

    # The lead-only options stay in the page (just hidden) when "No TeamShifts access"
    # is picked, so the browser still submits them together with the empty role.
    form = TeamForm(
        organizer=organizer,
        instance=team,
        data={
            'name': 'Shifts Team',
            'limit_events': [event.pk],
            'can_change_teams': 'on',
            'teamshifts_role': '',
            'all_teamshifts_roles': 'False',
            'limit_teamshifts_roles': [role.pk],
            'hide_teamshifts_emails': 'on',
        },
    )
    assert form.is_valid(), form.errors
    form.save()

    team.refresh_from_db()
    assert team.teamshifts_role == ''
    assert team.all_teamshifts_roles is False
    assert team.limit_teamshifts_roles == []
    assert team.hide_teamshifts_emails is False
