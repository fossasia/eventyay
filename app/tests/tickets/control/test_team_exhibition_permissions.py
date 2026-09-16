import pytest
from django.apps import apps
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer
from eventyay.control.forms.organizer_forms.team_form import TeamForm


EXHIBITION_FIELDS = (
    'can_change_exhibition_proposals',
    'is_exhibition_reviewer',
    'hide_exhibition_applicant_emails',
)


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='Exhibition Org', slug='exhibition-org')


def _event(organizer, slug, plugins=''):
    return Event.objects.create(
        organizer=organizer,
        name=slug,
        slug=slug,
        date_from=now(),
        plugins=plugins,
    )


@pytest.mark.django_db
def test_exhibition_permissions_hidden_when_no_event_enables_the_plugin(organizer):
    _event(organizer, 'plain')

    form = TeamForm(organizer=organizer)

    assert form.exhibition_plugin_enabled is False
    for field in EXHIBITION_FIELDS:
        assert field not in form.fields


@pytest.mark.django_db
@pytest.mark.skipif(not apps.is_installed('exhibition'), reason='exhibition plugin not installed')
def test_exhibition_permissions_shown_when_any_event_enables_the_plugin(organizer):
    _event(organizer, 'plain')
    _event(organizer, 'expo', plugins='exhibition')

    form = TeamForm(organizer=organizer)

    assert form.exhibition_plugin_enabled is True
    for field in EXHIBITION_FIELDS:
        assert field in form.fields


@pytest.mark.django_db
def test_hiding_the_fields_leaves_stored_permissions_untouched(organizer):
    _event(organizer, 'plain')
    team = organizer.teams.create(
        name='Reviewers',
        all_events=True,
        can_change_exhibition_proposals=True,
        is_exhibition_reviewer=True,
    )

    form = TeamForm(
        instance=team,
        organizer=organizer,
        data={'name': 'Reviewers', 'all_events': 'on', 'can_change_event_settings': 'on'},
    )
    assert form.is_valid(), form.errors
    form.save()

    team.refresh_from_db()
    assert team.can_change_exhibition_proposals is True
    assert team.is_exhibition_reviewer is True


@pytest.mark.django_db
@pytest.mark.skipif(not apps.is_installed('exhibition'), reason='exhibition plugin not installed')
def test_exhibition_only_team_rejected_when_its_events_lack_the_plugin(organizer):
    _event(organizer, 'expo', plugins='exhibition')
    plain = _event(organizer, 'plain')

    form = TeamForm(
        organizer=organizer,
        data={
            'name': 'Reviewers',
            'limit_events': [plain.pk],
            'can_change_exhibition_proposals': 'on',
        },
    )

    assert not form.is_valid()
    assert any('exhibition plugin enabled' in str(e) for e in form.non_field_errors())


@pytest.mark.django_db
@pytest.mark.skipif(not apps.is_installed('exhibition'), reason='exhibition plugin not installed')
def test_exhibition_only_team_accepted_for_an_exhibition_event(organizer):
    expo = _event(organizer, 'expo', plugins='exhibition')
    _event(organizer, 'plain')

    form = TeamForm(
        organizer=organizer,
        data={
            'name': 'Reviewers',
            'limit_events': [expo.pk],
            'can_change_exhibition_proposals': 'on',
        },
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
@pytest.mark.skipif(not apps.is_installed('exhibition'), reason='exhibition plugin not installed')
def test_other_permissions_still_allow_a_non_exhibition_event(organizer):
    _event(organizer, 'expo', plugins='exhibition')
    plain = _event(organizer, 'plain')

    form = TeamForm(
        organizer=organizer,
        data={
            'name': 'Settings',
            'limit_events': [plain.pk],
            'can_change_exhibition_proposals': 'on',
            'can_change_event_settings': 'on',
        },
    )

    assert form.is_valid(), form.errors
