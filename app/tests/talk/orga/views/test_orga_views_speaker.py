import json

import bs4
import pytest
from django_scopes import scope, scopes_disabled

from eventyay.base.models import SpeakerProfile, User
from eventyay.base.models.mail import QueuedMail
from eventyay.base.models.question import TalkQuestionRequired as QuestionRequired
from eventyay.orga.views.speaker import SpeakerViewMixin
from eventyay.person.forms import SpeakerProfileForm
from eventyay.person.forms.profile import AVATAR_LICENSE_TEXT_VALIDATION_ERROR


@pytest.mark.django_db
@pytest.mark.parametrize("query", ("", "?role=true", "?role=false", "?role=foobar"))
def test_orga_can_access_speakers_list(orga_client, speaker, event, submission, query):
    response = orga_client.get(event.orga_urls.speakers + query, follow=True)
    assert response.status_code == 200
    if not query:
        assert speaker.fullname in response.text


@pytest.mark.django_db
def test_orga_can_access_speaker_page(orga_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    assert speaker.fullname in response.text


@pytest.mark.django_db
def test_orga_can_change_speaker_password(orga_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.password_reset
        assert not speaker.pw_reset_token
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert not speaker.pw_reset_token
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert speaker.pw_reset_token


@pytest.mark.django_db
def test_reviewer_can_access_speaker_page(review_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
    response = review_client.get(url, follow=True)
    assert response.status_code == 200
    assert speaker.fullname in response.text


@pytest.mark.django_db
def test_reviewer_cannot_change_speaker_password(
    review_client, speaker, event, submission
):
    assert not speaker.pw_reset_token
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.password_reset
    response = review_client.post(url, follow=True)
    assert response.status_code == 404
    with scope(event=event):
        speaker.refresh_from_db()
        assert not speaker.pw_reset_token


@pytest.mark.django_db
def test_reviewer_cannot_access_speaker_page_with_deleted_submission(
    review_client, other_speaker, event, deleted_submission
):
    with scope(event=event):
        assert event.submissions.all().count() == 0
        assert event.submissions(manager="all_objects").count() == 1
        url = other_speaker.event_profile(event).orga_urls.base
    response = review_client.get(url, follow=True)
    assert response.status_code == 404
    assert other_speaker.fullname not in response.text


@pytest.mark.django_db
def test_orga_can_edit_speaker(orga_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
        profile = speaker.event_profile(event)
        count = profile.logged_actions().all().count()
    response = orga_client.post(
        url,
        data={
            "name": "BESTSPEAKAR",
            "biography": "I rule!",
            "email": "foo@foooobar.de",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert count + 1 == profile.logged_actions().all().count()
    assert speaker.fullname == "BESTSPEAKAR", response.text
    assert speaker.email == "foo@foooobar.de"


@pytest.mark.django_db
def test_speaker_profile_form_not_strict_allows_missing_required_fields(speaker, event):
    event.cfp.fields["avatar"]["visibility"] = "required"
    event.cfp.save()

    with scope(event=event):
        form = SpeakerProfileForm(
            data={
                "fullname": "",
                "email": "",
                "biography": "Draft bio",
            },
            event=event,
            user=speaker,
            not_strict=True,
        )

        assert form.is_valid()
        assert "fullname" not in form.errors
        assert "email" not in form.errors
        assert "avatar" not in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ("avatar_source", "avatar_license"))
def test_speaker_profile_rejects_long_avatar_license_text(field_name, speaker, event):
    with scope(event=event):
        form = SpeakerProfileForm(
            data={
                "fullname": speaker.fullname,
                "email": speaker.email,
                "biography": speaker.event_profile(event).biography,
                field_name: " ".join(["word"] * 3001),
            },
            event=event,
            user=speaker,
        )

        assert not form.is_valid()
        assert AVATAR_LICENSE_TEXT_VALIDATION_ERROR in str(form.errors[field_name])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name,license_text",
    (
        ("avatar_source", " ".join(["word"] * 3000)),
        ("avatar_license", " ".join(["word"] * 3000)),
        ("avatar_source", "Photo by Alice Example, used with permission"),
        ("avatar_license", "Licensed under CC BY-SA 4.0"),
    ),
)
def test_speaker_profile_accepts_valid_avatar_license_text(
    field_name, license_text, speaker, event
):
    with scope(event=event):
        form = SpeakerProfileForm(
            data={
                "fullname": speaker.fullname,
                "email": speaker.email,
                "biography": speaker.event_profile(event).biography,
                field_name: license_text,
            },
            event=event,
            user=speaker,
        )

        assert form.is_valid()
        assert form.cleaned_data[field_name] == license_text


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ("avatar_source", "avatar_license"))
def test_speaker_profile_rejects_encoded_avatar_license_text(
    field_name, speaker, event
):
    encoded_value = "data:image/png;base64," + ("A" * 600)
    with scope(event=event):
        form = SpeakerProfileForm(
            data={
                "fullname": speaker.fullname,
                "email": speaker.email,
                "biography": speaker.event_profile(event).biography,
                field_name: encoded_value,
            },
            event=event,
            user=speaker,
        )

        assert not form.is_valid()
        assert AVATAR_LICENSE_TEXT_VALIDATION_ERROR in str(form.errors[field_name])


@pytest.mark.django_db
def test_submission_speakers_wraps_avatar_license_text(orga_client, speaker, event, submission):
    payload = "data:image/png;base64," + ("A" * 600)
    with scope(event=event):
        speaker.avatar_source = payload
        speaker.avatar_license = payload
        speaker.save(update_fields=["avatar_source", "avatar_license"])

    response = orga_client.get(submission.orga_urls.speakers, follow=True)

    assert response.status_code == 200
    doc = bs4.BeautifulSoup(response.content, "lxml")
    for label in ("Profile Picture Source:", "Profile Picture License:"):
        element = doc.find("strong", string=label)
        assert element is not None
        wrapper = element.find_parent("p")
        assert wrapper is not None
        assert "avatar-license-text" in wrapper.get("class", [])


@pytest.mark.django_db
def test_orga_can_edit_speaker_unchanged(orga_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
        profile = speaker.event_profile(event)
        count = profile.logged_actions().all().count()
        event.cfp.fields["availabilities"]["visibility"] = "do_not_ask"
        event.cfp.save()
    response = orga_client.post(
        url,
        data={
            "name": speaker.fullname,
            "biography": profile.biography,
            "email": speaker.email,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert count == profile.logged_actions().all().count()


@pytest.mark.django_db
def test_orga_cannot_edit_speaker_without_filling_questions(
    orga_client, speaker, event, submission, speaker_question
):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
        speaker_question.question_required = QuestionRequired.REQUIRED
        speaker_question.save()
    response = orga_client.post(
        url,
        data={
            "name": "BESTSPEAKAR",
            "biography": "bio",
            "email": speaker.email,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
    assert speaker.fullname == "BESTSPEAKAR", response.text


@pytest.mark.django_db
def test_orga_cant_assign_duplicate_address(
    orga_client, speaker, event, submission, other_speaker
):
    event.cfp.fields["availabilities"]["visibility"] = "do_not_ask"
    event.cfp.save()
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
    response = orga_client.post(
        url,
        data={
            "name": "BESTSPEAKAR",
            "biography": "I rule!",
            "email": other_speaker.email,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
    assert speaker.fullname != "BESTSPEAKAR", response.text
    assert speaker.email != other_speaker.email


@pytest.mark.django_db
def test_orga_can_edit_speaker_status(orga_client, speaker, event, submission):
    with scopes_disabled():
        logs = speaker.logged_actions().count()
    with scope(event=event):
        assert speaker.profiles.first().has_arrived is False
        url = speaker.profiles.first().orga_urls.toggle_arrived
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert speaker.profiles.first().has_arrived is True
    with scopes_disabled():
        assert speaker.logged_actions().count() == logs + 1
    response = orga_client.get(url + "?from=list", follow=True)
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
        assert speaker.profiles.first().has_arrived is False
    with scopes_disabled():
        assert speaker.logged_actions().count() == logs + 2


@pytest.mark.django_db
def test_orga_can_toggle_speaker_featured(orga_client, speaker, event, submission):
    with scope(event=event):
        profile = speaker.event_profile(event)
        assert profile.is_featured is False
        url = profile.orga_urls.toggle_featured

    response = orga_client.post(url)
    assert response.status_code == 200

    with scope(event=event):
        profile.refresh_from_db()
        assert profile.is_featured is True

    response = orga_client.post(url)
    assert response.status_code == 200

    with scope(event=event):
        profile.refresh_from_db()
        assert profile.is_featured is False


@pytest.mark.django_db
def test_reviewer_cannot_toggle_speaker_featured(
    review_client, speaker, event, submission
):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.toggle_featured
    response = review_client.post(url, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_orga_can_reorder_speakers(
    orga_client, speaker, other_speaker, event, submission, other_submission
):
    with scope(event=event):
        first_profile = speaker.event_profile(event)
        second_profile = other_speaker.event_profile(event)
        assert first_profile.position is None
        assert second_profile.position is None

    response = orga_client.post(
        event.orga_urls.speakers,
        data={"order": f"{second_profile.pk},{first_profile.pk}"},
    )
    assert response.status_code == 204

    with scope(event=event):
        first_profile.refresh_from_db()
        second_profile.refresh_from_db()
        assert second_profile.position == 0
        assert first_profile.position == 1

    list_response = orga_client.get(event.orga_urls.speakers)
    assert list_response.status_code == 200
    assert list_response.text.index(other_speaker.fullname) < list_response.text.index(
        speaker.fullname
    )


@pytest.mark.django_db
def test_speaker_list_has_featured_and_drag_controls(
    orga_client, speaker, event, submission
):
    response = orga_client.get(event.orga_urls.speakers, follow=True)
    assert response.status_code == 200
    assert f'dragsort-url="{event.orga_urls.speakers}"' in response.text
    assert f'featured_speaker_{speaker.code}' in response.text
    assert "dragsort-button" in response.text


@pytest.mark.django_db
def test_speaker_list_sorts_by_featured(
    orga_client, speaker, other_speaker, event, submission, other_submission
):
    with scope(event=event):
        featured_profile = speaker.event_profile(event)
        featured_profile.is_featured = True
        featured_profile.save(update_fields=['is_featured'])

    response = orga_client.get(event.orga_urls.speakers + '?sort=-is_featured', follow=True)
    assert response.status_code == 200
    assert 'sort=-is_featured' in response.text or 'sort=%2Dis_featured' in response.text

    def speaker_names_in_table(response):
        doc = bs4.BeautifulSoup(response.content, 'lxml')
        table = doc.select_one('table tbody')
        assert table is not None
        return [link.get_text(strip=True) for link in table.select('td a[href*="/speakers/"]')]

    names = speaker_names_in_table(response)
    assert names[0] == speaker.fullname


@pytest.mark.django_db
def test_speaker_arrival_buttons_use_distinct_styles(orga_client, speaker, event, accepted_submission):
    with scope(event=event):
        profile = speaker.event_profile(event)
        profile.has_arrived = False
        profile.save(update_fields=['has_arrived'])

    response = orga_client.get(event.orga_urls.speakers, follow=True)
    assert response.status_code == 200
    assert 'btn-speaker-arrived' in response.text
    assert 'Mark speaker as arrived' in response.text

    profile.has_arrived = True
    with scope(event=event):
        profile.save(update_fields=['has_arrived'])
    response = orga_client.get(event.orga_urls.speakers, follow=True)
    assert 'btn-speaker-not-arrived' in response.text
    assert 'Mark speaker as not arrived' in response.text


@pytest.mark.django_db
def test_speaker_list_shows_linked_sessions(orga_client, speaker, event, submission):
    response = orga_client.get(event.orga_urls.speakers, follow=True)
    assert response.status_code == 200
    assert submission.title in response.text
    assert submission.orga_urls.base in response.text
    assert 'speaker-session-list' in response.text


@pytest.mark.django_db
def test_speaker_list_shows_session_state_badge(orga_client, speaker, event, submission):
    response = orga_client.get(event.orga_urls.speakers, follow=True)
    assert response.status_code == 200
    doc = bs4.BeautifulSoup(response.content, 'lxml')
    item = doc.select_one('.speaker-session-list li')
    assert item.select_one('a')['href'] == submission.orga_urls.base
    badge = item.select_one('.badge.submission-state')
    assert 'submission-state-submitted' in badge['class']
    assert 'submitted' in badge.text


@pytest.mark.django_db
def test_speaker_list_shows_one_state_badge_per_session(orga_client, speaker, event, submission, confirmed_submission):
    response = orga_client.get(event.orga_urls.speakers, follow=True)
    assert response.status_code == 200
    doc = bs4.BeautifulSoup(response.content, 'lxml')
    items = doc.select('.speaker-session-list li')
    assert len(items) == 2
    states = set()
    for item in items:
        badges = item.select('.badge.submission-state')
        assert len(badges) == 1
        states.update(badges[0]['class'])
    assert 'submission-state-submitted' in states
    assert 'submission-state-confirmed' in states


@pytest.mark.django_db
def test_speaker_arrived_toggle_from_list_stays_on_list(orga_client, speaker, event, accepted_submission):
    list_url = event.orga_urls.speakers + '?sort=-is_featured'
    with scope(event=event):
        toggle_url = speaker.event_profile(event).orga_urls.toggle_arrived
    response = orga_client.post(f'{toggle_url}?next={list_url}', follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'].rstrip('/').endswith('/speakers')
    assert 'sort=-is_featured' in response.request.get('QUERY_STRING', '')


@pytest.mark.django_db
def test_speaker_arrived_toggle_without_next_returns_to_list(orga_client, speaker, event, accepted_submission):
    with scope(event=event):
        toggle_url = speaker.event_profile(event).orga_urls.toggle_arrived
    response = orga_client.post(toggle_url, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'].rstrip('/').endswith('/speakers')


@pytest.mark.django_db
def test_reviewer_cannot_edit_speaker(review_client, speaker, event, submission):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.base
    response = review_client.post(
        url,
        data={"name": "BESTSPEAKAR", "biography": "I rule!"},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker.refresh_from_db()
    assert speaker.fullname != "BESTSPEAKAR", response.text


@pytest.mark.django_db
def test_orga_can_create_speaker_information(orga_client, event):
    with scope(event=event):
        assert event.information.all().count() == 0
    orga_client.post(
        event.orga_urls.new_information,
        data={
            "title_0": "Test Information",
            "text_0": "Very Important!!!",
            "target_group": "submitters",
        },
        follow=True,
    )
    with scope(event=event):
        assert event.information.all().count() == 1


@pytest.mark.django_db
def test_orga_can_edit_speaker_information(orga_client, event, information):
    orga_client.post(
        information.orga_urls.edit,
        data={
            "title_0": "Banana banana",
            "text_0": "Very Important!!!",
            "target_group": "submitters",
        },
        follow=True,
    )
    with scope(event=event):
        information.refresh_from_db()
        assert str(information.title) == "Banana banana"


@pytest.mark.django_db
def test_reviewer_cant_edit_speaker_information(review_client, event, information):
    review_client.post(
        information.orga_urls.edit,
        data={
            "title_0": "Banana banana",
            "text_0": "Very Important!!!",
            "target_group": "confirmed",
        },
        follow=True,
    )
    with scope(event=event):
        information.refresh_from_db()
        assert str(information.title) != "Banana banana"


@pytest.mark.django_db
def test_orga_can_delete_speaker_information(orga_client, event, information):
    with scope(event=event):
        assert event.information.all().count() == 1
    orga_client.post(information.orga_urls.delete, follow=True)
    with scope(event=event):
        assert event.information.all().count() == 0


@pytest.mark.django_db
def test_orga_cant_export_answers_csv_empty(orga_client, speaker, event, submission):
    response = orga_client.post(
        event.orga_urls.speakers + "export/",
        data={
            "target": "rejected",
            "name": "on",
            "export_format": "csv",
        },
    )
    assert response.status_code == 200
    assert response.text.strip().startswith(
        "<!DOCTYPE"
    )  # HTML response instead of empty download


@pytest.mark.django_db
def test_orga_cant_export_answers_csv_without_delimiter(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "speaker"
        answered_choice_question.save()
    response = orga_client.post(
        event.orga_urls.speakers + "export/",
        data={
            "target": "all",
            "name": "on",
            f"question_{answered_choice_question.id}": "on",
            "export_format": "csv",
        },
    )
    assert response.status_code == 200
    assert response.text.strip().startswith("<!DOCTYPE")


@pytest.mark.django_db
def test_orga_can_export_answers_csv(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "speaker"
        answered_choice_question.save()
        answer = answered_choice_question.answers.all().first().answer_string
    response = orga_client.post(
        event.orga_urls.speakers + "export/",
        data={
            "target": "all",
            "name": "on",
            f"question_{answered_choice_question.id}": "on",
            "submission_ids": "on",
            "export_format": "csv",
            "data_delimiter": "comma",
        },
    )
    assert response.status_code == 200
    assert (
        response.text
        == f"ID,Name,Proposal IDs,{answered_choice_question.question}\r\n{speaker.code},{speaker.fullname},{submission.code},{answer}\r\n"
    )


@pytest.mark.django_db
def test_orga_can_export_answers_json(
    orga_client, speaker, event, submission, answered_choice_question
):
    with scope(event=event):
        answered_choice_question.target = "speaker"
        answered_choice_question.save()
        answer = answered_choice_question.answers.all().first().answer_string
    response = orga_client.post(
        event.orga_urls.speakers + "export/",
        data={
            "target": "all",
            "name": "on",
            f"question_{answered_choice_question.id}": "on",
            "submission_ids": "on",
            "export_format": "json",
        },
    )
    assert response.status_code == 200
    assert json.loads(response.text) == [
        {
            "ID": speaker.code,
            "Name": speaker.fullname,
            answered_choice_question.question: answer,
            "Proposal IDs": [submission.code],
        }
    ]


@pytest.mark.django_db
def test_orga_speakers_list_has_add_speaker_button(orga_client, event):
    response = orga_client.get(event.orga_urls.speakers)
    assert response.status_code == 200
    assert "Add speaker" in response.text
    assert event.orga_urls.new_speaker in response.text


@pytest.mark.django_db
def test_orga_can_create_speaker_with_email(orga_client, event):
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "New Speaker",
            "email": "new.speaker@example.org",
            "biography": "New biography text",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        profile = SpeakerProfile.objects.filter(
            event=event, user__email="new.speaker@example.org"
        ).first()
        assert profile is not None
        assert profile.user.submissions.filter(event=event).count() == 0


@pytest.mark.django_db
def test_orga_can_create_speaker_without_email(orga_client, event):
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "No Email Speaker",
            "no_email": "on",
            "biography": "New biography text",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        profile = SpeakerProfile.objects.filter(
            event=event, user__fullname="No Email Speaker"
        ).first()
        assert profile is not None
        assert not profile.user.email
        assert not QueuedMail.objects.filter(event=event, to_users=profile.user).exists()


@pytest.mark.django_db
def test_orga_create_speaker_form_includes_no_email_option(orga_client, event):
    response = orga_client.get(event.orga_urls.new_speaker)
    assert response.status_code == 200
    assert "This speaker does not require an email" in response.text
    assert 'id="id_no_email"' in response.text


@pytest.mark.django_db
def test_cfp_speaker_profile_form_does_not_expose_no_email(event, speaker):
    """Regression: no_email must stay orga-create-only and never leak onto public forms."""
    with scope(event=event):
        public_form = SpeakerProfileForm(event=event, user=speaker)
        assert "no_email" not in public_form.fields
        assert "no_email" not in public_form.as_p()

        create_form = SpeakerProfileForm(
            event=event, user=None, allow_no_email=True, ignore_first_time_exclude=True
        )
        assert "no_email" in create_form.fields


@pytest.mark.django_db
def test_speaker_profile_form_ignores_no_email_post_without_allow_flag(event, speaker):
    with scope(event=event):
        form = SpeakerProfileForm(
            event=event,
            user=speaker,
            data={
                "fullname": speaker.fullname,
                "email": "",
                "no_email": "on",
                "biography": "Still required to look valid",
            },
        )
        assert "no_email" not in form.fields
        assert not form.is_valid()


@pytest.mark.django_db
def test_orga_can_create_speaker_with_new_session(orga_client, event):
    with scope(event=event):
        submission_type = event.submission_types.first()
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Session Speaker",
            "email": "session.speaker@example.org",
            "biography": "New biography text",
            "add_session": "on",
            "session-title": "New Session Title",
            "session-abstract": "Session abstract",
            "session-description": "Session description",
            "session-content_locale": "en",
            "session-duration": "",
            "session-slot_count": 1,
            "session-notes": "",
            "session-internal_notes": "",
            "session-submission_type": submission_type.pk,
            "session-state": "submitted",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        profile = SpeakerProfile.objects.filter(
            event=event, user__email="session.speaker@example.org"
        ).first()
        assert profile is not None
        assert event.submissions.filter(
            title="New Session Title", speakers=profile.user
        ).exists()


@pytest.mark.django_db
def test_orga_can_create_speaker_without_email_with_session(orga_client, event):
    with scope(event=event):
        submission_type = event.submission_types.first()
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "VIP Keynote",
            "no_email": "on",
            "biography": "Keynote biography",
            "add_session": "on",
            "session-title": "VIP Keynote Session",
            "session-abstract": "Abstract",
            "session-description": "Description",
            "session-content_locale": "en",
            "session-duration": "",
            "session-slot_count": 1,
            "session-notes": "",
            "session-internal_notes": "",
            "session-submission_type": submission_type.pk,
            "session-state": "submitted",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        profile = SpeakerProfile.objects.filter(event=event, user__fullname="VIP Keynote").first()
        assert profile is not None
        assert not profile.user.email
        assert event.submissions.filter(
            title="VIP Keynote Session", speakers=profile.user
        ).exists()
        assert not QueuedMail.objects.filter(event=event, to_users=profile.user).exists()


@pytest.mark.django_db
def test_orga_can_create_speaker_and_link_existing_session(orga_client, event, submission):
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Linked Speaker",
            "email": "linked.speaker@example.org",
            "biography": "New biography text",
            "link_existing_session": "on",
            "existing_session_id": submission.pk,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        profile = SpeakerProfile.objects.filter(
            event=event, user__email="linked.speaker@example.org"
        ).first()
        assert profile is not None
        submission.refresh_from_db()
        assert profile.user in submission.speakers.all()


@pytest.mark.django_db
def test_orga_link_flag_without_session_does_not_create_speaker(orga_client, event):
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Conflict Speaker",
            "email": "conflict@example.org",
            "biography": "New biography text",
            "link_existing_session": "on",
        },
    )
    assert response.status_code == 200
    assert "Please select an existing session to link." in response.text
    with scope(event=event):
        assert not SpeakerProfile.objects.filter(
            event=event, user__email="conflict@example.org"
        ).exists()


@pytest.mark.django_db
def test_orga_can_link_multiple_sessions_and_create_one(
    orga_client, event, submission, other_submission
):
    with scope(event=event):
        submission_type = event.submission_types.first()
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Multi Session Speaker",
            "email": "multi.session@example.org",
            "biography": "New biography text",
            "add_session": "on",
            "existing_session_id": [submission.pk, other_submission.pk],
            "session-title": "Brand New Session",
            "session-abstract": "Session abstract",
            "session-description": "Session description",
            "session-content_locale": "en",
            "session-duration": "",
            "session-slot_count": 1,
            "session-notes": "",
            "session-internal_notes": "",
            "session-submission_type": submission_type.pk,
            "session-state": "submitted",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        profile = SpeakerProfile.objects.filter(
            event=event, user__email="multi.session@example.org"
        ).first()
        assert profile is not None
        submission.refresh_from_db()
        other_submission.refresh_from_db()
        assert profile.user not in submission.speakers.all()
        assert profile.user not in other_submission.speakers.all()
        assert event.submissions.filter(
            title="Brand New Session", speakers=profile.user
        ).exists()




@pytest.mark.django_db
def test_orga_cannot_create_speaker_with_unassociated_global_user_email(orga_client, event):
    with scopes_disabled():
        outsider = User.objects.create_user(
            email="outsider@example.org",
            password="speakerpwd1!",
            fullname="Outside User",
        )
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Global Speaker",
            "email": outsider.email,
            "biography": "New biography text",
        },
    )
    assert response.status_code == 200
    assert "not associated with this event" in response.text
    with scope(event=event):
        assert not SpeakerProfile.objects.filter(event=event, user=outsider).exists()


@pytest.mark.django_db
def test_orga_can_create_speaker_with_associated_user_email(orga_client, event):
    with scopes_disabled():
        teammate = User.objects.create_user(
            email="teammate@example.org",
            password="speakerpwd1!",
            fullname="Team Mate",
        )
    with scope(event=event):
        event.organizer.teams.first().members.add(teammate)

    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Associated Speaker",
            "email": teammate.email,
            "biography": "New biography text",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert SpeakerProfile.objects.filter(event=event, user=teammate).exists()


@pytest.mark.django_db
def test_orga_cannot_create_speaker_without_email_when_required(orga_client, event):
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Missing Email Speaker",
            "email": "",
            "biography": "Biography text",
        },
    )
    assert response.status_code == 200
    assert "This field is required." in response.text
    with scope(event=event):
        assert not SpeakerProfile.objects.filter(
            event=event, user__fullname="Missing Email Speaker"
        ).exists()


@pytest.mark.django_db
def test_orga_cannot_create_speaker_with_empty_biography_when_required(orga_client, event):
    with scope(event=event):
        event.cfp.fields["biography"]["visibility"] = "required"
        event.cfp.save(update_fields=["fields"])
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Empty Bio Speaker",
            "email": "empty@example.org",
            "biography": "",
        },
    )
    assert response.status_code == 200
    assert "This field is required." in response.text
    with scope(event=event):
        assert not SpeakerProfile.objects.filter(
            event=event, user__email="empty@example.org"
        ).exists()


@pytest.mark.django_db
def test_standalone_speaker_appears_on_speakers_list(orga_client, event):
    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Standalone Visible",
            "email": "standalone.visible@example.org",
            "biography": "Visible without a session",
        },
        follow=True,
    )
    assert response.status_code == 200
    list_response = orga_client.get(event.orga_urls.speakers)
    assert list_response.status_code == 200
    assert "Standalone Visible" in list_response.text


@pytest.mark.django_db
def test_speaker_view_mixin_get_object_establishes_scope(rf, event, speaker, orga_user):
    with scopes_disabled():
        request = rf.get("/")
        request.event = event
        request.user = orga_user

        mixin = SpeakerViewMixin()
        mixin.request = request
        mixin.kwargs = {"code": speaker.code}

        obj = mixin.get_object()
        assert obj == speaker


@pytest.mark.django_db
def test_orga_can_create_speaker_with_custom_field(orga_client, event, speaker_question):
    with scope(event=event):
        speaker_question.target = "speaker"
        speaker_question.save(update_fields=["target"])

    response = orga_client.post(
        event.orga_urls.new_speaker,
        data={
            "fullname": "Custom Field Speaker",
            "email": "custom.field@example.org",
            "biography": "Has a custom field answer",
            f"question_{speaker_question.id}": "My custom answer",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        profile = SpeakerProfile.objects.filter(
            event=event, user__email="custom.field@example.org"
        ).first()
        assert profile is not None
        assert profile.answers.filter(question=speaker_question, answer="My custom answer").exists()
