import datetime as dt

import pytest
from django.core import mail as djmail
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models.event import Event
from eventyay.base.models.organizer import Organizer

@pytest.mark.django_db
def test_orga_create_organiser(administrator_client):
    assert len(Organizer.objects.all()) == 0
    response = administrator_client.post(
        "/orga/organizer/new",
        data={
            "name_0": "The bestest organiser",
            "name_1": "The bestest organiser",
            "slug": "organiser",
        },
        follow=True,
    )
    assert response.status_code == 200, response.text
    assert len(Organizer.objects.all()) == 1
    organiser = Organizer.objects.all().first()
    assert str(organiser.name) == "The bestest organiser", response.text
    assert str(organiser) == str(organiser.name)


@pytest.mark.django_db
def test_orga_edit_organiser(orga_client, organiser):
    response = orga_client.post(
        organiser.orga_urls.settings,
        data={"name_0": "The bestest organiser", "name_1": "The bestest organiser"},
        follow=True,
    )
    organiser.refresh_from_db()
    assert response.status_code == 200, response.text
    assert str(organiser.name) == "The bestest organiser", response.text
    assert str(organiser) == str(organiser.name)


@pytest.mark.django_db
def test_orga_see_organiser(orga_client, organiser):
    response = orga_client.get(organiser.orga_urls.base)
    organiser.refresh_from_db()
    assert response.status_code == 200, response.text
    assert str(organiser.name) in response.text
    assert str(organiser) == str(organiser.name)


@pytest.mark.django_db
def test_orga_edit_team(orga_client, organiser, event):
    team = organiser.teams.first()
    url = reverse(
        "orga:organiser.teams.update",
        kwargs={"organiser": organiser.slug, "pk": team.pk},
    )
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        url,
        follow=True,
        data={
            "all_events": True,
            "can_change_submissions": True,
            "can_change_organizer_settings": True,
            "can_change_event_settings": True,
            "can_change_teams": True,
            "can_create_events": True,
            "form": "team",
            "limit_events": event.pk,
            "name": "Fancy New Name",
        },
    )
    assert response.status_code == 200
    team.refresh_from_db()
    assert team.name == "Fancy New Name"


@pytest.mark.django_db
def test_orga_edit_team_illegal(orga_client, organiser, event):
    team = organiser.teams.first()
    url = reverse(
        "orga:organiser.teams.update",
        kwargs={"organiser": organiser.slug, "pk": team.pk},
    )
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        url,
        follow=True,
        data={
            "all_events": True,
            "can_change_submissions": True,
            "can_change_organizer_settings": False,
            "can_change_event_settings": True,
            "can_change_teams": False,
            "can_create_events": True,
            "form": "team",
            "limit_events": event.pk,
            "name": "Fancy New Name",
        },
    )
    assert response.status_code == 200
    team.refresh_from_db()
    assert team.name != "Fancy New Name"
    assert team.can_change_teams
    assert team.can_change_organizer_settings


@pytest.mark.django_db
@pytest.mark.parametrize("is_administrator", [True, False])
def test_orga_create_team(orga_client, organiser, event, is_administrator, orga_user):
    orga_user.is_administrator = is_administrator
    orga_user.save()
    count = organiser.teams.count()
    response = orga_client.get(organiser.orga_urls.new_team, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        organiser.orga_urls.new_team,
        follow=True,
        data={
            "all_events": True,
            "can_change_submissions": True,
            "can_change_organizer_settings": True,
            "can_change_event_settings": True,
            "can_change_teams": True,
            "can_create_events": True,
            "form": "team",
            "limit_events": event.pk,
            "name": "Fancy New Name",
            "organiser": organiser.pk,
        },
    )
    assert response.status_code == 200
    assert organiser.teams.count() == count + 1, response.text


@pytest.mark.django_db
def test_orga_create_team_without_event(orga_client, organiser, event, orga_user):
    orga_user.is_administrator = True
    orga_user.save()
    count = organiser.teams.count()
    response = orga_client.get(organiser.orga_urls.new_team, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        organiser.orga_urls.new_team,
        follow=True,
        data={
            "can_change_submissions": True,
            "can_change_organizer_settings": True,
            "can_change_event_settings": True,
            "can_change_teams": True,
            "can_create_events": True,
            "form": "team",
            "name": "Fancy New Name",
            "organiser": organiser.pk,
        },
    )
    assert response.status_code == 200
    assert organiser.teams.count() == count


@pytest.mark.django_db
def test_invite_orga_member_as_orga(orga_client, organiser):
    djmail.outbox = []
    team = organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    url = reverse(
        "orga:organiser.teams.update",
        kwargs={"organiser": organiser.slug, "pk": team.pk},
    )
    assert team.members.count() == 1
    assert team.invites.count() == 0
    response = orga_client.post(
        url, {"invite-email": "other@user.org", "form": "invite"}, follow=True
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ["other@user.org"]


@pytest.mark.django_db
def test_invite_multiple_orga_members_as_orga(orga_client, organiser):
    djmail.outbox = []
    team = organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    url = reverse(
        "orga:organiser.teams.update",
        kwargs={"organiser": organiser.slug, "pk": team.pk},
    )
    assert team.members.count() == 1
    assert team.invites.count() == 0
    response = orga_client.post(
        url,
        {
            "invite-bulk_email": "first@pretalx.org\nsecond@pretalx.org",
            "form": "invite",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 2
    assert len(djmail.outbox) == 2
    assert djmail.outbox[0].to == ["first@pretalx.org"]
    assert djmail.outbox[1].to == ["second@pretalx.org"]


@pytest.mark.django_db
def test_resend_invite(orga_client, organiser, invitation):
    djmail.outbox = []
    team = invitation.team
    assert team.members.count() == 1
    assert team.invites.count() == 1
    url = reverse(
        "orga:organiser.teams.invites.resend",
        kwargs={"organiser": organiser.slug, "pk": team.pk, "invite_pk": invitation.pk},
    )
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1
    assert len(djmail.outbox) == 0

    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == [invitation.email]


@pytest.mark.django_db
def test_reset_team_member_password(orga_client, organiser, other_orga_user):
    djmail.outbox = []
    team = organiser.teams.get(can_change_submissions=False, is_reviewer=True)
    team.members.add(other_orga_user)
    team.save()
    member = team.members.first()
    assert not member.pw_reset_token
    url = organiser.orga_urls.teams + f"{team.pk}/members/{member.pk}/reset/"
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.pw_reset_token
    reset_token = member.pw_reset_token
    assert len(djmail.outbox) == 1

    response = orga_client.post(
        url, follow=True
    )  # make sure we can do this twice despite timeouts
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.pw_reset_token != reset_token
    reset_token = member.pw_reset_token
    assert len(djmail.outbox) == 2


@pytest.mark.django_db
def test_remove_other_team_member_but_not_last_member(
    orga_client, orga_user, organiser, other_orga_user
):
    team = organiser.teams.filter(can_change_teams=True).first()
    team.members.add(other_orga_user)
    team.save()
    assert team.members.all().count() == 2

    url = organiser.orga_urls.teams + f"{team.pk}/members/{other_orga_user.pk}/delete/"
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert team.members.all().count() == 1

    url = organiser.orga_urls.teams + f"{team.pk}/members/{orga_user.pk}/delete/"
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert team.members.all().count() == 1


@pytest.mark.django_db
def test_organiser_cannot_delete_organiser(event, orga_client, submission):
    assert Event.objects.count() == 1
    assert Organizer.objects.count() == 1
    response = orga_client.post(event.organizer.orga_urls.delete, follow=True)
    assert response.status_code == 404
    assert Event.objects.count() == 1
    assert Organizer.objects.count() == 1


@pytest.mark.django_db
def test_administrator_can_delete_organiser(event, administrator_client, submission):
    assert Event.objects.count() == 1
    assert Organizer.objects.count() == 1
    response = administrator_client.get(event.organizer.orga_urls.delete, follow=True)
    assert response.status_code == 200
    response = administrator_client.post(event.organizer.orga_urls.delete, follow=True)
    assert response.status_code == 200
    assert Event.objects.count() == 0
    assert Organizer.objects.count() == 0
