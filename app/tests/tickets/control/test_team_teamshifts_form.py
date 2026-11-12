import pytest
from django.apps import apps
from django.http import QueryDict
from django.utils.timezone import now
from django_scopes import scope

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
    with scope(event=event):
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


@pytest.mark.django_db
def test_team_form_removes_teamshifts_role_when_submitted_role_was_deleted(organizer, event, teamshifts_installed):
    with scope(event=event):
        role = apps.get_model('teamshifts', 'TeamRole').objects.create(event=event, name='Stewards')
    team = Team.objects.create(
        organizer=organizer,
        name='Shifts Team',
        can_change_teams=True,
        teamshifts_role='lead',
        all_teamshifts_roles=False,
        limit_teamshifts_roles=[role.pk],
    )
    team.limit_events.add(event)
    stale_pk = role.pk
    with scope(event=event):
        role.delete()

    form = TeamForm(
        organizer=organizer,
        instance=team,
        data={
            'name': 'Shifts Team',
            'limit_events': [event.pk],
            'can_change_teams': 'on',
            'teamshifts_role': '',
            'limit_teamshifts_roles': [stale_pk],
        },
    )
    assert form.is_valid(), form.errors
    form.save()

    team.refresh_from_db()
    assert team.teamshifts_role == ''
    assert team.limit_teamshifts_roles == []


def _checkbox_post(event, *role_values):
    data = QueryDict(mutable=True)
    data.update({'name': 'Shifts Team', 'can_change_teams': 'on'})
    data.setlist('limit_events', [str(event.pk)])
    data.setlist('teamshifts_role', ['', *role_values])
    return data


@pytest.fixture
def lead_team(organizer, event):
    team = Team.objects.create(
        organizer=organizer,
        name='Shifts Team',
        can_change_teams=True,
        teamshifts_role='lead',
        hide_teamshifts_emails=True,
    )
    team.limit_events.add(event)
    return team


@pytest.mark.django_db
@pytest.mark.parametrize(
    'submitted, expected',
    (
        (('coordinator',), 'coordinator'),
        (('lead',), 'lead'),
        (('coordinator', 'lead'), 'lead'),
    ),
)
def test_ticked_teamshifts_checkbox_sets_the_role(
    organizer, event, lead_team, teamshifts_installed, submitted, expected
):
    data = _checkbox_post(event, *submitted)
    data['all_teamshifts_roles'] = 'True'
    form = TeamForm(organizer=organizer, instance=lead_team, data=data)
    assert form.is_valid(), form.errors
    form.save()

    lead_team.refresh_from_db()
    assert lead_team.teamshifts_role == expected
