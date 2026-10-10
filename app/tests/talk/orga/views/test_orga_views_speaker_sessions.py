import bs4
import pytest
from django_scopes import scope

from eventyay.base.models import SpeakerInvitation


SPEAKER_DATA = {
    "fullname": "Jane Speaker",
    "email": "jane@speaker.org",
    "biography": "Speaker biography",
}


def speaker_url(speaker, event):
    with scope(event=event):
        return speaker.event_profile(event).orga_urls.base


@pytest.mark.django_db
def test_existing_speaker_page_offers_session_options(orga_client, event, speaker, submission, other_submission):
    response = orga_client.get(speaker_url(speaker, event))
    assert response.status_code == 200
    page = bs4.BeautifulSoup(response.text, "html.parser")
    assert page.select_one("#id_add_session") is not None
    assert page.select_one("#existing_session_section") is not None
    options = page.select("#id_existing_session_id option")
    values = {option["value"] for option in options}
    assert str(other_submission.pk) in values
    assert str(submission.pk) not in values


@pytest.mark.django_db
def test_existing_speaker_can_be_linked_to_existing_session(orga_client, event, speaker, submission, other_submission):
    response = orga_client.post(
        speaker_url(speaker, event),
        data={**SPEAKER_DATA, "link_existing_session": "on", "existing_session_id": other_submission.pk},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert other_submission.speakers.filter(pk=speaker.pk).exists()
        assert other_submission.logged_actions().filter(action_type="eventyay.submission.speakers.add").exists()


@pytest.mark.django_db
def test_existing_sessions_respect_team_track_limits(
    orga_client, orga_user, event, speaker, submission, other_submission, track, other_track
):
    with scope(event=event):
        other_submission.track = track
        other_submission.save()
        orga_user.teams.first().limit_tracks.add(other_track)
    response = orga_client.get(speaker_url(speaker, event))
    options = bs4.BeautifulSoup(response.text, "html.parser").select("#id_existing_session_id option")
    values = {option["value"] for option in options}
    assert str(other_submission.pk) not in values


@pytest.mark.django_db
def test_new_session_tracks_respect_team_track_limits(
    orga_client, orga_user, event, speaker, submission, track, other_track
):
    with scope(event=event):
        submission.track = track
        submission.save()
        orga_user.teams.first().limit_tracks.add(track)
    response = orga_client.get(speaker_url(speaker, event))
    page = bs4.BeautifulSoup(response.text, "html.parser")
    options = page.select("#session_section select[name=session-track] option")
    values = {option["value"] for option in options}
    assert str(track.pk) in values
    assert str(other_track.pk) not in values


@pytest.mark.django_db
def test_existing_speaker_can_get_a_new_session(orga_client, event, speaker, submission, track):
    with scope(event=event):
        submission_type = event.submission_types.first()
    response = orga_client.post(
        speaker_url(speaker, event),
        data={
            **SPEAKER_DATA,
            "add_session": "on",
            "session-title": "Brand New Session",
            "session-state": "submitted",
            "session-abstract": "Session abstract",
            "session-track": track.pk,
            "session-submission_type": submission_type.pk,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.submissions.filter(title="Brand New Session", speakers=speaker).exists()


@pytest.mark.django_db
def test_existing_speaker_cannot_link_a_session_twice(orga_client, event, speaker, submission):
    response = orga_client.post(
        speaker_url(speaker, event),
        data={**SPEAKER_DATA, "link_existing_session": "on", "existing_session_id": submission.pk},
    )
    assert response.status_code == 200
    assert "The selected session does not exist." in response.text


@pytest.mark.django_db
def test_new_session_replaces_linking_existing_session(
    orga_client, event, speaker, submission, other_submission, track
):
    with scope(event=event):
        submission_type = event.submission_types.first()
    response = orga_client.post(
        speaker_url(speaker, event),
        data={
            **SPEAKER_DATA,
            "add_session": "on",
            "existing_session_id": other_submission.pk,
            "session-title": "Brand New Session",
            "session-state": "submitted",
            "session-abstract": "Session abstract",
            "session-track": track.pk,
            "session-submission_type": submission_type.pk,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.submissions.filter(title="Brand New Session", speakers=speaker).exists()
        assert not other_submission.speakers.filter(pk=speaker.pk).exists()


@pytest.mark.django_db
def test_session_edit_page_lists_speakers_with_add_and_remove(orga_client, event, speaker, submission):
    response = orga_client.get(submission.orga_urls.edit)
    assert response.status_code == 200
    page = bs4.BeautifulSoup(response.text, "html.parser")
    section = page.select_one("[data-session-speakers]")
    assert section is not None
    assert speaker.get_display_name() in section.text
    actions = {form["action"].split("?")[0] for form in section.select("form")}
    assert submission.orga_urls.speakers in actions
    assert submission.orga_urls.delete_speaker in actions
    assert section.select_one("[name=email]") is not None
    assert section.select_one("[name=name]") is not None


@pytest.mark.django_db
def test_speaker_linked_from_speaker_page_shows_on_session_page(
    orga_client, event, speaker, submission, other_submission
):
    orga_client.post(
        speaker_url(speaker, event),
        data={**SPEAKER_DATA, "link_existing_session": "on", "existing_session_id": other_submission.pk},
    )
    response = orga_client.get(other_submission.orga_urls.edit)
    section = bs4.BeautifulSoup(response.text, "html.parser").select_one("[data-session-speakers]")
    assert "Jane Speaker" in section.text


@pytest.mark.django_db
def test_session_page_adds_existing_speaker(orga_client, event, speaker, other_submission):
    response = orga_client.post(
        other_submission.orga_urls.speakers,
        data={"email": speaker.email, "name": speaker.fullname},
    )
    assert response.status_code == 302
    with scope(event=event):
        assert other_submission.speakers.filter(pk=speaker.pk).exists()
    response = orga_client.get(speaker_url(speaker, event))
    assert other_submission.title in response.text


@pytest.mark.django_db
def test_session_page_removes_speaker(orga_client, event, speaker, submission):
    response = orga_client.post(submission.orga_urls.delete_speaker, data={"id": speaker.pk})
    assert response.status_code == 302
    with scope(event=event):
        assert not submission.speakers.filter(pk=speaker.pk).exists()


@pytest.mark.django_db
def test_session_page_speaker_changes_return_to_next_url(orga_client, event, speaker, submission, other_submission):
    next_url = other_submission.orga_urls.edit
    response = orga_client.post(
        f"{other_submission.orga_urls.speakers}?next={next_url}",
        data={"email": speaker.email, "name": speaker.fullname},
    )
    assert response.status_code == 302
    assert response.url == next_url
    response = orga_client.post(f"{submission.orga_urls.delete_speaker}?next={next_url}", data={"id": speaker.pk})
    assert response.status_code == 302
    assert response.url == next_url


@pytest.mark.django_db
def test_session_page_ignores_external_next_url(orga_client, event, speaker, submission):
    response = orga_client.post(
        f"{submission.orga_urls.delete_speaker}?next=https://example.com/",
        data={"id": speaker.pk},
    )
    assert response.status_code == 302
    assert response.url == submission.orga_urls.speakers


@pytest.mark.django_db
def test_session_page_invites_new_speaker_and_lists_invitation(orga_client, event, submission):
    edit_url = submission.orga_urls.edit
    response = orga_client.post(
        f"{submission.orga_urls.speakers}?next={edit_url}",
        data={"email": "new.speaker@example.org", "name": "New Speaker"},
    )
    assert response.status_code == 302
    assert response.url == edit_url
    response = orga_client.get(edit_url)
    section = bs4.BeautifulSoup(response.text, "html.parser").select_one("[data-session-speakers]")
    assert "New Speaker" in section.text
    assert "Pending" in section.text


@pytest.mark.django_db
def test_session_page_revokes_pending_invitation(orga_client, event, submission):
    with scope(event=event):
        invitation = SpeakerInvitation.objects.create(
            submission=submission, email="cospeaker@example.org", name="Co Speaker"
        )
    edit_url = submission.orga_urls.edit
    revoke_url = bs4.BeautifulSoup(orga_client.get(edit_url).text, "html.parser").select_one(
        "[data-session-speakers] form[action*='revoke']"
    )["action"]
    response = orga_client.post(revoke_url)
    assert response.status_code == 302
    assert response.url.startswith(edit_url)
    with scope(event=event):
        assert not submission.speaker_invitations.filter(pk=invitation.pk, status="pending").exists()
