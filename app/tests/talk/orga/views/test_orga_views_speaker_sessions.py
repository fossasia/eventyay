import bs4
import pytest
from django_scopes import scope


SPEAKER_DATA = {
    "fullname": "Jane Speaker",
    "email": "jane@speaker.org",
    "biography": "Speaker biography",
}


def speaker_url(speaker, event):
    with scope(event=event):
        return speaker.event_profile(event).orga_urls.base


@pytest.mark.django_db
def test_new_speaker_form_uses_new_session_label(orga_client, event):
    response = orga_client.get(event.orga_urls.new_speaker)
    assert response.status_code == 200
    assert "Create a new session for this speaker" in response.text
    assert "Also create a new session for this speaker" not in response.text
    assert "Link an existing session instead" in response.text


@pytest.mark.django_db
def test_existing_speaker_page_offers_session_options(orga_client, event, speaker, submission, other_submission):
    response = orga_client.get(speaker_url(speaker, event))
    assert response.status_code == 200
    assert "Create a new session for this speaker" in response.text
    assert "Link an existing session instead" in response.text
    options = bs4.BeautifulSoup(response.text, "html.parser").select("#id_existing_session_id option")
    values = {option["value"] for option in options}
    assert str(other_submission.pk) in values
    assert str(submission.pk) not in values


@pytest.mark.django_db
def test_existing_speaker_can_be_linked_to_existing_session(orga_client, event, speaker, other_submission):
    response = orga_client.post(
        speaker_url(speaker, event),
        data={**SPEAKER_DATA, "link_existing_session": "on", "existing_session_id": other_submission.pk},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert other_submission.speakers.filter(pk=speaker.pk).exists()


@pytest.mark.django_db
def test_existing_speaker_can_get_a_new_session(orga_client, event, speaker, track):
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
def test_existing_speaker_cannot_create_and_link_at_once(orga_client, event, speaker, other_submission):
    response = orga_client.post(
        speaker_url(speaker, event),
        data={
            **SPEAKER_DATA,
            "add_session": "on",
            "link_existing_session": "on",
            "existing_session_id": other_submission.pk,
        },
    )
    assert response.status_code == 200
    assert "You cannot both create a new session and link an existing session." in response.text
    with scope(event=event):
        assert not other_submission.speakers.filter(pk=speaker.pk).exists()


@pytest.mark.django_db
def test_session_edit_page_lists_speakers_with_add_and_remove(orga_client, event, speaker, submission):
    response = orga_client.get(submission.orga_urls.edit)
    assert response.status_code == 200
    page = bs4.BeautifulSoup(response.text, "html.parser")
    section = page.select_one("[data-session-speakers]")
    assert section is not None
    assert speaker.get_display_name() in section.text
    actions = {form["action"] for form in section.select("form")}
    assert submission.orga_urls.speakers in actions
    assert submission.orga_urls.delete_speaker in actions
    assert section.select_one("[name=email]") is not None
    assert section.select_one("[name=name]") is not None


@pytest.mark.django_db
def test_speaker_linked_from_speaker_page_shows_on_session_page(orga_client, event, speaker, other_submission):
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
