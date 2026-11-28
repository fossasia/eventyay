import pytest
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.models import Team


@pytest.fixture(autouse=True)
def site_settings(settings):
    settings.SITE_URL = 'https://testserver'
    settings.EVENTYAY_OBLIGATORY_2FA = False


@pytest.fixture
@scopes_disabled()
def video_team(organizer, event):
    team = Team.objects.create(
        organizer=organizer,
        name='Video crew',
        can_change_teams=True,
        can_create_events=True,
        can_view_orders=True,
        can_video_moderate=True,
        can_change_event_settings=True,
    )
    team.limit_events.add(event)
    return team


def _teams_url(organizer):
    return reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})


@pytest.mark.django_db
def test_duplicate_prefills_only_selected_sections(organizer_client, organizer, event, video_team):
    response = organizer_client.get(_teams_url(organizer), {'duplicate': video_team.pk, 'copy': ['events', 'video']})
    assert response.status_code == 200
    form = response.context['team_create_form']
    assert response.context['duplicate_source'] == video_team
    assert form.initial['name'] == 'Video crew (copy)'
    assert form.initial['limit_events'] == [event.pk]
    assert form.initial['can_change_event_settings'] is True
    assert form.initial['can_video_moderate'] is True
    assert 'can_view_orders' not in form.initial
    assert 'can_create_events' not in form.initial


@pytest.mark.django_db
def test_duplicate_panel_leaves_organizer_permissions_unchecked(organizer_client, organizer, video_team):
    response = organizer_client.get(_teams_url(organizer))
    sections = {section['key']: section for section in response.context['duplicate_sections']}
    assert sections['organizer']['checked'] is False
    assert sections['events']['checked'] is True
    assert response.context['duplicate_source'] is None


@pytest.mark.django_db
def test_duplicate_ignores_teams_of_other_organizers(organizer_client, organizer):
    from eventyay.base.models import Organizer

    with scopes_disabled():
        other = Organizer.objects.create(name='Other', slug='other')
        foreign = Team.objects.create(organizer=other, name='Foreign', can_change_teams=True)
    response = organizer_client.get(_teams_url(organizer), {'duplicate': foreign.pk, 'copy': ['organizer']})
    assert response.context['duplicate_source'] is None
    assert 'name' not in response.context['team_create_form'].initial


@pytest.mark.django_db
def test_duplicate_opens_create_form_without_saving(organizer_client, organizer, video_team):
    response = organizer_client.get(_teams_url(organizer), {'duplicate': video_team.pk, 'copy': ['video']})
    content = response.content.decode()
    assert 'id="create-team-form" class="collapse in"' in content
    assert 'value="Video crew (copy)"' in content
    with scopes_disabled():
        assert not Team.objects.filter(organizer=organizer, name='Video crew (copy)').exists()
