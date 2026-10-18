import datetime as dt
import json
import re
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import pytest
from django.apps import apps
from django.conf import settings
from django.core import mail as djmail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError, connection, connections, transaction
from django.test import TransactionTestCase
from django_scopes import scope

from eventyay.base.models import Answer, Event, QueuedMail, Track
from eventyay.base.models import TalkQuestion as Question
from eventyay.base.models.question import TalkQuestionRequired as QuestionRequired


_FORM_OPEN = re.compile(r"<form(?:\s|>)", re.I)
_FORM_CLOSE = re.compile(r"</form\s*>", re.I)


def _max_form_nesting(html: str) -> int:
    """Return the greatest number of nested form elements in the rendered page."""
    events = [(match.start(), 1) for match in _FORM_OPEN.finditer(html)]
    events += [(match.start(), -1) for match in _FORM_CLOSE.finditer(html)]
    depth = max_depth = 0
    for _, delta in sorted(events):
        depth += delta
        max_depth = max(max_depth, depth)
    return max_depth


@pytest.mark.django_db
def test_edit_cfp(orga_client, event):
    response = orga_client.post(
        event.cfp.urls.edit_text,
        {
            "headline_0": "new headline",
            "text_0": "",
            "deadline": "2000-10-10 20:20",
            "count_length_in": "chars",
            "settings-cfp_ask_abstract": "required",
            "settings-cfp_ask_description": "do_not_ask",
            "settings-cfp_ask_notes": "optional",
            "settings-cfp_ask_biography": "optional",
            "settings-cfp_ask_avatar": "optional",
            "settings-cfp_ask_availabilities": "optional",
            "settings-cfp_ask_do_not_record": "optional",
            "settings-cfp_ask_image": "optional",
            "settings-cfp_ask_track": "optional",
            "settings-cfp_ask_duration": "optional",
            "settings-cfp_ask_additional_speaker": "optional",
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert str(event.cfp.headline) == ""
    assert response.status_code == 200


@pytest.mark.django_db
def test_edit_cfp_timezones(orga_client, event):
    event = Event.objects.get(slug=event.slug)
    event.timezone = "Europe/Berlin"
    event.save()
    event.cfp.deadline = dt.datetime(2018, 3, 5, 17, 39, 15, tzinfo=ZoneInfo("UTC"))
    event.cfp.save()
    response = orga_client.get(event.cfp.urls.edit_text)
    assert response.status_code == 200
    assert "2018-03-05T18:39" in response.rendered_content
    assert "2018-03-05T17:39" not in response.rendered_content


@pytest.mark.django_db
def test_edit_cfp_flow(orga_client, event):
    response = orga_client.get(event.cfp.urls.editor)
    assert response.status_code == 200, response.text
    response = orga_client.post(
        event.cfp.urls.editor, {"action": "reset"}, content_type="application/json"
    )
    assert response.status_code == 200, response.text
    response = orga_client.post(
        event.cfp.urls.editor,
        "not actually useful data",
        content_type="application/json",
    )
    assert response.status_code == 400, response.text
    with scope(event=event):
        response = orga_client.post(
            event.cfp.urls.editor,
            event.cfp_flow.get_editor_config(json_compat=True),
            content_type="application/json",
        )
    assert response.status_code == 200, response.text


@pytest.mark.django_db
def test_edit_cfp_flow_shows_in_frontend(orga_client, event):
    with scope(event=event):
        new_config = event.cfp_flow.get_editor_config(json_compat=True)

    new_config[0]["title"]["en"] = "TEST CFP WOO"
    new_config[0]["text"]["en"] = "PLS SUBMIT HERE THX"
    new_config[0]["fields"][0]["help_text"]["en"] = "titles are hard, y'know"
    response = orga_client.post(
        event.cfp.urls.editor,
        new_config,
        content_type="application/json",
    )
    assert response.status_code == 200, response.text

    response = orga_client.get(event.cfp.urls.submit, follow=True)
    assert response.status_code == 200
    assert "TEST CFP WOO" in response.text
    assert "PLS SUBMIT HERE THX" in response.text
    assert "titles are hard, y'know" in response.text


@pytest.mark.django_db
def test_make_submission_type_default(
    orga_client, submission_type, default_submission_type
):
    with scope(event=submission_type.event):
        assert default_submission_type.event.submission_types.count() == 2
        assert submission_type.event.cfp.default_type == default_submission_type
    response = orga_client.post(submission_type.urls.default, follow=True)
    assert response.status_code == 200
    with scope(event=submission_type.event):
        assert default_submission_type.event.submission_types.count() == 2
        submission_type.event.cfp.refresh_from_db()
        assert submission_type.event.cfp.default_type == submission_type


@pytest.mark.django_db
def test_make_submission_type_default_rejects_get(
    orga_client, submission_type, default_submission_type
):
    with scope(event=submission_type.event):
        assert submission_type.event.cfp.default_type == default_submission_type
    response = orga_client.get(submission_type.urls.default)
    assert response.status_code == 405
    with scope(event=submission_type.event):
        submission_type.event.cfp.refresh_from_db()
        assert submission_type.event.cfp.default_type == default_submission_type


@pytest.mark.django_db
def test_edit_submission_type(orga_client, submission_type):
    with scope(event=submission_type.event):
        count = submission_type.logged_actions().count()
    response = orga_client.post(
        submission_type.urls.edit,
        {"default_duration": 31, "slug": "New_Type", "name_0": "New Type!"},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=submission_type.event):
        assert count + 1 == submission_type.logged_actions().count()
        submission_type.refresh_from_db()
    assert submission_type.default_duration == 31
    assert str(submission_type.name) == "New Type!"


@pytest.mark.django_db
def test_edit_submission_type_without_change(orga_client, submission_type):
    with scope(event=submission_type.event):
        count = submission_type.logged_actions().count()
    response = orga_client.post(
        submission_type.urls.edit,
        {
            "default_duration": submission_type.default_duration,
            "slug": submission_type.slug,
            "name_0": str(submission_type.name),
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=submission_type.event):
        assert count == submission_type.logged_actions().count()


@pytest.mark.django_db
def test_delete_submission_type(orga_client, submission_type, default_submission_type):
    with scope(event=submission_type.event):
        assert default_submission_type.event.submission_types.count() == 2
    response = orga_client.get(submission_type.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=submission_type.event):
        assert default_submission_type.event.submission_types.count() == 2
    response = orga_client.post(submission_type.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=submission_type.event):
        assert default_submission_type.event.submission_types.count() == 1


@pytest.mark.django_db
def test_delete_used_submission_type(
    orga_client, event, submission_type, default_submission_type, submission
):
    with scope(event=event):
        assert submission_type.event.submission_types.count() == 2
        submission.submission_type = submission_type
        submission.save()
    response = orga_client.post(submission_type.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert submission_type.event.submission_types.count() == 2


@pytest.mark.django_db
def test_delete_last_submission_type(orga_client, event):
    submission_type = event.cfp.default_type
    with scope(event=event):
        assert submission_type.event.submission_types.count() == 1
    response = orga_client.post(submission_type.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert submission_type.event.submission_types.count() == 1


@pytest.mark.django_db
def test_delete_default_submission_type(
    orga_client, submission_type, default_submission_type
):
    with scope(event=submission_type.event):
        assert default_submission_type.event.submission_types.count() == 2
    response = orga_client.post(default_submission_type.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=submission_type.event):
        assert default_submission_type.event.submission_types.count() == 2


@pytest.mark.django_db
def test_all_questions_in_list(orga_client, question, inactive_question, event):
    with scope(event=event):
        assert event.questions.count() == 1
        assert Question.all_objects.filter(event=event).count() == 2
    response = orga_client.get(event.cfp.urls.questions, follow=True)
    assert question.question in response.text
    assert inactive_question.question in response.text


@pytest.mark.django_db
def test_delete_question(orga_client, event, question):
    with scope(event=event):
        assert event.questions.count() == 1
    response = orga_client.get(question.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.questions.count() == 1
    response = orga_client.post(question.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.questions.count() == 0
        assert Question.all_objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_delete_inactive_question(orga_client, event, inactive_question):
    with scope(event=event):
        assert Question.all_objects.filter(event=event).count() == 1
    response = orga_client.post(inactive_question.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.questions.count() == 0
        assert Question.all_objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_delete_choice_question(orga_client, event, choice_question):
    with scope(event=event):
        assert Question.all_objects.filter(event=event).count() == 1
    response = orga_client.post(choice_question.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.questions.count() == 0
        assert Question.all_objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_cannot_delete_answered_question(orga_client, event, answered_choice_question):
    with scope(event=event):
        assert event.questions.count() == 1
        assert answered_choice_question.answers.count() == 1
        assert answered_choice_question.options.count() == 3
    response = orga_client.post(answered_choice_question.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        answered_choice_question = Question.all_objects.get(
            pk=answered_choice_question.pk
        )
        assert answered_choice_question
        assert not answered_choice_question.active
        assert event.questions.count() == 0
        assert answered_choice_question.answers.count() == 1
        assert answered_choice_question.options.count() == 3


@pytest.mark.django_db
def test_can_add_simple_question(orga_client, event):
    with scope(event=event):
        assert event.questions.count() == 0
    response = orga_client.post(
        event.cfp.urls.new_question,
        {
            "target": "submission",
            "question_0": "What is your name?",
            "variant": "string",
            "active": True,
            "help_text_0": "Answer if you want to reach the other side!",
            "question_required": QuestionRequired.OPTIONAL,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        event.refresh_from_db()
        assert event.questions.count() == 1
        q = event.questions.first()
        assert str(q.question) == "What is your name?"
        assert q.variant == "string"
    response = orga_client.get(q.urls.base + "?role=true", follow=True)
    with scope(event=event):
        assert str(q.question) in response.text
    response = orga_client.get(q.urls.base + "?role=false", follow=True)
    with scope(event=event):
        assert str(q.question) in response.text


@pytest.mark.django_db
def test_can_add_simple_question_required_freeze(orga_client, event):
    with scope(event=event):
        assert event.questions.count() == 0
    response = orga_client.post(
        event.cfp.urls.new_question,
        {
            "target": "submission",
            "question_0": "What is your name?",
            "variant": "string",
            "active": True,
            "help_text_0": "Answer if you want to reach the other side!",
            "question_required": QuestionRequired.REQUIRED,
            "freeze_after": "2021-06-22T12:44:42Z",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        event.refresh_from_db()
        assert event.questions.count() == 1
        q = event.questions.first()
        assert str(q.question) == "What is your name?"
        assert q.variant == "string"
    response = orga_client.get(q.urls.base + "?role=true", follow=True)
    with scope(event=event):
        assert str(q.question) in response.text
    response = orga_client.get(q.urls.base + "?role=false", follow=True)
    with scope(event=event):
        assert str(q.question) in response.text


@pytest.mark.django_db
def test_can_add_simple_question_after_deadline(orga_client, event):
    with scope(event=event):
        assert event.questions.count() == 0
    response = orga_client.post(
        event.cfp.urls.new_question,
        {
            "target": "submission",
            "question_0": "What is your name?",
            "variant": "string",
            "active": True,
            "help_text_0": "Answer if you want to reach the other side!",
            "question_required": QuestionRequired.AFTER_DEADLINE,
            "deadline": "2021-06-22T12:44:42Z",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        event.refresh_from_db()
        assert event.questions.count() == 1
        q = event.questions.first()
        assert str(q.question) == "What is your name?"
        assert q.variant == "string"
        assert q.deadline == dt.datetime(
            2021, 6, 22, 12, 44, 42, tzinfo=ZoneInfo("UTC")
        )
    response = orga_client.get(q.urls.base + "?role=true", follow=True)
    with scope(event=event):
        assert str(q.question) in response.text
    response = orga_client.get(q.urls.base + "?role=false", follow=True)
    with scope(event=event):
        assert str(q.question) in response.text


@pytest.mark.django_db
def test_can_add_simple_question_after_deadline_missing_deadline(orga_client, event):
    with scope(event=event):
        assert event.questions.count() == 0
    orga_client.post(
        event.cfp.urls.new_question,
        {
            "target": "submission",
            "question_0": "What is your name?",
            "variant": "string",
            "active": True,
            "help_text_0": "Answer if you want to reach the other side!",
            "question_required": QuestionRequired.AFTER_DEADLINE,
        },
        follow=True,
    )
    with scope(event=event):
        event.refresh_from_db()
        assert event.questions.count() == 0


@pytest.mark.django_db
def test_can_add_choice_question(orga_client, event):
    with scope(event=event):
        assert event.questions.count() == 0
    response = orga_client.post(
        event.cfp.urls.new_question,
        {
            "target": "submission",
            "question_0": "Is it an African or a European swallow?",
            "variant": "choices",
            "active": True,
            "help_text_0": "Answer if you want to reach the other side!",
            "form-TOTAL_FORMS": 2,
            "form-INITIAL_FORMS": 0,
            "form-0-id": "",
            "form-0-answer_0": "African",
            "form-1-id": "",
            "form-1-answer_0": "European",
            "form-2-id": "",
            "form-2-answer_0": "",
            "question_required": QuestionRequired.OPTIONAL,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        event.refresh_from_db()
        assert event.questions.count() == 1
        q = event.questions.first()
        assert q.variant == "choices"
        assert q.options.count() == 2


@pytest.mark.django_db
def test_can_edit_choice_question(orga_client, event, choice_question):
    with scope(event=event):
        count = choice_question.options.count()
        assert str(choice_question.options.first().answer) != "African"
        first_option = choice_question.options.first().pk
        last_option = choice_question.options.last().pk
        other_option = choice_question.options.all()[1]
        other_answer = str(other_option.answer)
    response = orga_client.post(
        choice_question.urls.edit,
        {
            "target": "submission",
            "question_0": "Is it an African or a European swallow?",
            "variant": "choices",
            "active": True,
            "help_text_0": "Answer if you want to reach the other side!",
            "form-TOTAL_FORMS": 3,
            "form-INITIAL_FORMS": 3,
            "form-0-id": first_option,
            "form-0-answer_0": "African",
            "form-1-id": last_option,
            "form-1-answer_0": "European",
            "form-2-id": other_option.pk,
            "form-2-answer_0": other_answer,
            "form-2-DELETE": "on",
            "form-3-id": "",
            "form-3-answer_0": "",
            "question_required": QuestionRequired.OPTIONAL,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        event.refresh_from_db()
        assert event.questions.count() == 1
        assert choice_question.variant == "choices"
        assert choice_question.options.count() == count - 1
        assert str(choice_question.options.first().answer) == "African"


@pytest.mark.parametrize("role,count", (("accepted", 1), ("confirmed", 1), ("", 2)))
@pytest.mark.django_db
def test_can_remind_speaker_question(
    orga_client,
    event,
    speaker_question,
    review_question,
    speaker,
    slot,
    other_speaker,
    other_submission,
    role,
    count,
):
    with scope(event=event):
        original_count = QueuedMail.objects.count()
    response = orga_client.post(
        event.cfp.urls.remind_questions, {"role": role}, follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.count() == original_count + count


@pytest.mark.parametrize("role,count", (("accepted", 1), ("confirmed", 1), ("", 2)))
@pytest.mark.django_db
def test_can_remind_submission_question(
    orga_client,
    event,
    question,
    speaker,
    slot,
    other_speaker,
    other_submission,
    role,
    count,
):
    with scope(event=event):
        original_count = QueuedMail.objects.count()
    response = orga_client.post(
        event.cfp.urls.remind_questions, {"role": role}, follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.count() == original_count + count


@pytest.mark.parametrize("role,count", (("accepted", 1), ("confirmed", 1), ("", 2)))
@pytest.mark.django_db
def test_can_remind_multiple_questions(
    orga_client,
    event,
    question,
    speaker_question,
    speaker,
    slot,
    other_speaker,
    other_submission,
    role,
    count,
):
    with scope(event=event):
        original_count = QueuedMail.objects.count()
    response = orga_client.post(
        event.cfp.urls.remind_questions, {"role": role}, follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.count() == original_count + count


@pytest.mark.django_db
def test_can_remind_submission_question_broken_filter(
    orga_client,
    event,
):
    response = orga_client.post(
        event.cfp.urls.remind_questions, {"role": "hahaha"}, follow=True
    )
    assert response.status_code == 200
    assert "Could not send mails" in response.text


@pytest.mark.parametrize("role,count", (("accepted", 0), ("confirmed", 0), ("", 0)))
@pytest.mark.django_db
def test_can_remind_answered_submission_question(
    orga_client,
    event,
    question,
    speaker,
    slot,
    other_speaker,
    other_submission,
    role,
    count,
):
    with scope(event=event):
        from eventyay.base.models.question import Answer

        question.question_required = QuestionRequired.REQUIRED
        question.deadline = None
        question.save()
        original_count = QueuedMail.objects.count()
        Answer.objects.create(
            submission=slot.submission,
            question=question,
            person=speaker,
            answer="something",
        )
        Answer.objects.create(
            submission=other_submission,
            question=question,
            person=other_speaker,
            answer="something",
        )
    response = orga_client.post(
        event.cfp.urls.remind_questions, {"role": role}, follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.count() == original_count + count


@pytest.mark.django_db
def test_can_hide_question(orga_client, question):
    assert question.active

    response = orga_client.post(question.urls.toggle, follow=True)
    with scope(event=question.event):
        question = Question.all_objects.get(pk=question.pk)

    assert response.status_code == 200
    assert not question.active


@pytest.mark.django_db
def test_hide_question_rejects_get(orga_client, question):
    assert question.active
    response = orga_client.get(question.urls.toggle)
    with scope(event=question.event):
        question = Question.all_objects.get(pk=question.pk)
    assert response.status_code == 405
    assert question.active


@pytest.mark.django_db
def test_can_hide_question_via_json(orga_client, question):
    assert question.active
    response = orga_client.post(
        question.urls.toggle,
        data=json.dumps({"field": "active", "value": False}),
        content_type="application/json",
    )
    with scope(event=question.event):
        question = Question.all_objects.get(pk=question.pk)
    assert response.status_code == 200
    assert not question.active


@pytest.mark.django_db
def test_question_edit_toggle_form_is_not_nested(orga_client, question):
    response = orga_client.get(question.urls.edit)
    assert response.status_code == 200
    html = response.content.decode()
    assert question.urls.toggle in html
    assert _max_form_nesting(html) <= 1


@pytest.mark.django_db
def test_can_activate_inactive_question(orga_client, inactive_question):
    assert not inactive_question.active

    response = orga_client.post(inactive_question.urls.toggle, follow=True)
    inactive_question.refresh_from_db()

    assert response.status_code == 200
    assert inactive_question.active


@pytest.mark.django_db
def test_can_see_tracks(orga_client, track):
    response = orga_client.get(track.event.cfp.urls.tracks)
    assert response.status_code == 200
    assert track.name in response.text


@pytest.mark.django_db
def test_can_see_single_track(orga_client, track):
    response = orga_client.get(track.urls.base)
    assert response.status_code == 200
    assert track.name in response.text


@pytest.mark.django_db
def test_can_edit_track(orga_client, track):
    with scope(event=track.event):
        count = track.logged_actions().count()
    response = orga_client.post(
        track.urls.base, {"name_0": "Name", "color": "#ffff99"}, follow=True
    )
    assert response.status_code == 200
    with scope(event=track.event):
        assert track.logged_actions().count() == count + 1
        track.refresh_from_db()
    assert str(track.name) == "Name"


@pytest.mark.django_db
def test_can_edit_track_without_changes(orga_client, track):
    with scope(event=track.event):
        count = track.logged_actions().count()
    response = orga_client.post(
        track.urls.base, {"name_0": str(track.name), "color": track.color}, follow=True
    )
    assert response.status_code == 200
    with scope(event=track.event):
        assert track.logged_actions().count() == count


@pytest.mark.django_db
def test_cannot_set_incorrect_track_color(orga_client, track):
    response = orga_client.post(
        track.urls.base, {"name_0": "Name", "color": "#fgff99"}, follow=True
    )
    assert response.status_code == 200
    track.refresh_from_db()
    assert str(track.name) != "Name"


@pytest.mark.django_db
def test_can_delete_single_track(orga_client, track, event):
    response = orga_client.get(track.urls.delete)
    assert response.status_code == 200
    with scope(event=event):
        assert event.tracks.count() == 1
    response = orga_client.post(track.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.tracks.count() == 0


@pytest.mark.django_db
def test_cannot_delete_used_track(orga_client, track, event, submission):
    response = orga_client.get(track.urls.delete)
    assert response.status_code == 200
    with scope(event=event):
        assert event.tracks.count() == 1
        submission.track = track
        submission.save()
    response = orga_client.post(track.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.tracks.count() == 1


@pytest.mark.django_db
def test_can_see_access_codes(orga_client, access_code):
    response = orga_client.get(access_code.event.cfp.urls.access_codes)
    assert response.status_code == 200
    assert access_code.code in response.text


@pytest.mark.django_db
def test_can_see_single_access_code(orga_client, access_code):
    response = orga_client.get(access_code.urls.edit)
    assert response.status_code == 200
    assert access_code.code in response.text


@pytest.mark.django_db
def test_can_create_access_code(orga_client, event):
    with scope(event=event):
        assert event.submitter_access_codes.all().count() == 0
    response = orga_client.get(event.cfp.urls.new_access_code, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        event.cfp.urls.new_access_code, {"code": "LOLCODE"}, follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.submitter_access_codes.get(code="LOLCODE")


@pytest.mark.django_db
def test_cannot_create_access_code_with_forbidden_characters(orga_client, event):
    with scope(event=event):
        assert event.submitter_access_codes.all().count() == 0
    response = orga_client.get(event.cfp.urls.new_access_code, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        event.cfp.urls.new_access_code, {"code": "LOL %CODE"}, follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.submitter_access_codes.all().count() == 0


@pytest.mark.django_db
def test_can_edit_access_code(orga_client, access_code):
    with scope(event=access_code.event):
        count = access_code.logged_actions().count()
    response = orga_client.post(access_code.urls.edit, {"code": "LOLCODE"}, follow=True)
    assert response.status_code == 200
    with scope(event=access_code.event):
        access_code.refresh_from_db()
        assert access_code.logged_actions().count() == count + 1
    assert access_code.code == "LOLCODE"


@pytest.mark.django_db
def test_can_edit_access_code_without_change(orga_client, access_code):
    with scope(event=access_code.event):
        count = access_code.logged_actions().count()
    response = orga_client.post(
        access_code.urls.edit,
        {"code": access_code.code, "maximum_uses": access_code.maximum_uses},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=access_code.event):
        access_code.refresh_from_db()
        assert access_code.logged_actions().count() == count


@pytest.mark.django_db
def test_can_delete_single_access_code(orga_client, access_code, event):
    response = orga_client.get(access_code.urls.delete)
    assert response.status_code == 200
    with scope(event=event):
        assert event.submitter_access_codes.count() == 1
    response = orga_client.post(access_code.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.submitter_access_codes.count() == 0


@pytest.mark.django_db
def test_cannot_delete_used_access_code(orga_client, access_code, event, submission):
    with scope(event=event):
        assert event.submitter_access_codes.count() == 1
        submission.access_code = access_code
        submission.save()
    response = orga_client.post(access_code.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.submitter_access_codes.count() == 1


@pytest.mark.django_db
def test_can_send_access_code(orga_client, access_code):
    djmail.outbox = []
    response = orga_client.get(access_code.urls.send, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        access_code.urls.send,
        {"to": "test@example.com", "text": "test test", "subject": "test"},
        follow=True,
    )
    assert response.status_code == 200
    assert len(djmail.outbox) == 1
    mail = djmail.outbox[0]
    assert mail.to == ["test@example.com"]
    assert mail.body == "test test"
    assert mail.subject == "test"


@pytest.mark.django_db
def test_can_send_special_access_code(orga_client, access_code, track):
    access_code.track = track
    access_code.valid_until = access_code.event.datetime_from
    access_code.maximum_uses = 3
    access_code.save()
    djmail.outbox = []
    response = orga_client.get(access_code.urls.send, follow=True)
    assert response.status_code == 200

@pytest.mark.django_db
@pytest.mark.parametrize("restriction", ("matching", "other", "unrestricted"))
@pytest.mark.parametrize("target", ("submission", "speaker"))
@pytest.mark.parametrize("answered", (False, True))
def test_question_reminders_respect_track_restrictions(
    orga_client, event, question, submission, speaker, track, restriction, answered, target
):
    with scope(event=event):
        question.target = target
        question.save(update_fields=["target"])
        submission.track = track
        submission.save(update_fields=["track"])
        if restriction == "matching":
            question.tracks.add(track)
        elif restriction == "other":
            question.tracks.add(Track.objects.create(event=event, name="Other track"))
        if answered:
            Answer.objects.create(
                question=question, answer="Answered",
                submission=submission if target == "submission" else None,
                person=speaker if target == "speaker" else None,
            )
        existing_ids = list(QueuedMail.objects.values_list("pk", flat=True))
    response = orga_client.post(
        event.cfp.urls.remind_questions,
        {"role": "", "track": track.pk, "questions": [question.pk]},
    )
    assert response.status_code == 302
    with scope(event=event):
        reminders = QueuedMail.objects.exclude(pk__in=existing_ids)
        assert reminders.count() == int(restriction != "other" and not answered)


@pytest.mark.django_db
@pytest.mark.parametrize("target", ("submission", "speaker"))
@pytest.mark.parametrize("answered", (False, True))
def test_question_reminders_include_trackless_submissions(
    orga_client, event, question, submission, speaker, track, target, answered
):
    """Trackless submissions remain eligible for restricted, unanswered questions."""
    with scope(event=event):
        submission.track = None
        submission.save(update_fields=["track"])
        question.target = target
        question.save(update_fields=["target"])
        question.tracks.add(track)
        if answered:
            Answer.objects.create(
                question=question, answer="Answered",
                submission=submission if target == "submission" else None,
                person=speaker if target == "speaker" else None,
            )
        existing_ids = list(QueuedMail.objects.values_list("pk", flat=True))
    response = orga_client.post(
        event.cfp.urls.remind_questions,
        {"role": "", "questions": [question.pk]},
    )
    assert response.status_code == 302
    with scope(event=event):
        reminders = QueuedMail.objects.exclude(pk__in=existing_ids)
        assert reminders.count() == int(not answered)


@pytest.mark.django_db
def test_orga_cfp_forms_shows_session_videos_as_organizer_only(orga_client, event):
    """Identify the session video field as available only to organisers."""
    response = orga_client.get(event.cfp.urls.questions, follow=True)
    assert response.status_code == 200
    content = response.text
    assert "cfp-organizer-only-label" in content
    assert "Session videos" in content
    assert "Organizer only" in content
    assert "This field can only be edited by organizers."
    assert (
        "This field can only be edited by organizers. "
        "It is not displayed on the proposal form."
    ) in content


@pytest.mark.django_db
@pytest.mark.parametrize('variant', ('choices', 'multiple_choice', 'select'))
@pytest.mark.parametrize('mode', ('translated-append', 'translated-replace', 'plain-append'))
def test_upload_question_options_preserves_translations_and_answers(
    orga_client, event, submission, speaker, variant, mode
):
    """Import options through the organiser form without losing existing answers."""
    multilingual = mode != 'plain-append'
    event.locale_array = 'en,de' if multilingual else 'en'
    event.save()
    with scope(event=event):
        question = Question.objects.create(
            event=event,
            question='Meal preference',
            variant=variant,
            target='submission',
            question_required=QuestionRequired.OPTIONAL,
        )
        existing = question.options.create(
            answer={'en': 'Vegetarian', 'de': 'Vegetarisch'} if multilingual else {'en': 'Vegetarian'}, position=5
        )
        retained = question.options.create(
            answer={'en': 'Kosher', 'de': 'Koscher'} if multilingual else {'en': 'Kosher'}, position=12
        )
        retained.refresh_from_db()
        answer = Answer.objects.create(question=question, submission=submission, person=speaker)
        answer.options.add(existing)
        uploaded = [
            {'de': 'Vegetarisch', 'en': 'Vegetarian'},
            {'en': 'Vegan', 'de': 'Vegan'},
        ]
        if mode != 'translated-replace':
            uploaded.extend(
                [
                    {'de': 'Vegan', 'en': 'Vegan'},
                    {'en': 'Halal', 'de': 'Halal'},
                    {'en': 'Vegetarian', 'de': 'Vegetarisch'},
                ]
            )
        content = json.dumps(uploaded) if multilingual else 'Vegan\nVegan\nVegetarian\nHalal\nVegan'
        data = {
            'target': 'submission',
            'question_0': 'Meal preference',
            'variant': variant,
            'question_required': QuestionRequired.OPTIONAL,
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-0-id': existing.pk,
            'form-0-position': existing.position,
            'form-0-answer_0': 'Vegetarian',
            'form-1-id': retained.pk,
            'form-1-position': retained.position,
            'form-1-answer_0': 'Kosher',
        }
        if multilingual:
            german_index = [code for code, _ in settings.LANGUAGES].index('de')
            data.update(
                {
                    f'question_{german_index}': '',
                    f'form-0-answer_{german_index}': 'Vegetarisch',
                    f'form-1-answer_{german_index}': 'Koscher',
                }
            )
        if mode == 'translated-replace':
            data['options_replace'] = 'on'
        for _ in range(2 if mode != 'translated-replace' else 1):
            data['options'] = SimpleUploadedFile('options.json', content.encode())
            response = orga_client.post(question.urls.edit, data)
            assert response.status_code == 302, response.context_data['form'].errors
            if mode != 'translated-replace':
                assert question.options.count() == 4
                assert list(question.options.order_by('position').values_list('position', flat=True)) == [5, 12, 13, 14]
                assert question.options.filter(pk=retained.pk).exists()
                assert list(answer.options.values_list('pk', flat=True)) == [existing.pk]
            else:
                assert question.options.count() == 2
                assert not question.answers.exists()
            if multilingual:
                assert {tuple(sorted(option.answer.data.items())) for option in question.options.all()} == {
                    tuple(sorted(option.items()))
                    for option in (uploaded if mode == 'translated-replace' else uploaded + [retained.answer.data])
                }
            else:
                assert {str(option.answer) for option in question.options.all()} == {
                    'Vegetarian',
                    'Kosher',
                    'Vegan',
                    'Halal',
                }


@pytest.mark.django_db
@pytest.mark.parametrize('variant', ('choices', 'multiple_choice', 'select'))
def test_upload_translated_options_with_matching_default_labels(orga_client, event, variant):
    """Keep choices distinct when only their non-default translations differ."""
    event.locale_array = 'en,de'
    event.save()
    with scope(event=event):
        question = Question.objects.create(
            event=event,
            question='Choose a label',
            variant=variant,
            target='submission',
            question_required=QuestionRequired.OPTIONAL,
        )
        existing = question.options.create(answer={'en': 'Other', 'de': 'Andere'}, position=1)
        german_index = [code for code, _ in settings.LANGUAGES].index('de')
        translated = {'en': 'Other', 'de': 'Sonstige'}
        response = orga_client.post(
            question.urls.edit,
            {
                'target': 'submission',
                'question_0': 'Choose a label',
                'variant': variant,
                'question_required': QuestionRequired.OPTIONAL,
                'form-TOTAL_FORMS': 1,
                'form-INITIAL_FORMS': 1,
                'form-0-id': existing.pk,
                'form-0-position': existing.position,
                'form-0-answer_0': 'Other',
                f'form-0-answer_{german_index}': 'Andere',
                'options': SimpleUploadedFile('options.json', json.dumps([translated]).encode()),
            },
        )
        assert response.status_code == 302
        assert question.options.count() == 2
        existing.refresh_from_db()
        assert existing.answer.data == {'en': 'Other', 'de': 'Andere'}
        assert question.options.exclude(pk=existing.pk).get().answer.data == translated


class TestConcurrentQuestionOptionUploads(TransactionTestCase):
    """Exercise PostgreSQL request locking with cleanup for the legacy tables."""

    available_apps = [app.name for app in apps.get_app_configs()]

    @pytest.fixture(autouse=True)
    def bind_fixtures(self, client, mocker, request):
        """Provide the existing organiser fixtures to the Django transaction test."""
        mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
        self.client = client
        self.fixture_request = request

    @pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row-lock contention.')
    def test_append_requests_wait_for_question_save(self):
        """A competing upload waits for the question update before reading its choices."""
        event = self.fixture_request.getfixturevalue('event')
        self.user = self.fixture_request.getfixturevalue('orga_user')
        self.client.force_login(self.user)
        event.locale_array = 'en,de'
        event.save()
        with scope(event=event):
            question = Question.objects.create(
                event=event,
                question='Meal preference',
                variant='choices',
                target='submission',
                question_required=QuestionRequired.OPTIONAL,
            )
            existing = question.options.create(answer={'en': 'Vegetarian', 'de': 'Vegetarisch'}, position=9)
            german_index = [code for code, _ in settings.LANGUAGES].index('de')
            data = {
                'target': 'submission',
                'question_0': 'Meal preference',
                'variant': 'choices',
                'question_required': QuestionRequired.OPTIONAL,
                'form-TOTAL_FORMS': 1,
                'form-INITIAL_FORMS': 1,
                'form-0-id': existing.pk,
                'form-0-position': 9,
                'form-0-answer_0': 'Vegetarian',
                f'form-0-answer_{german_index}': 'Vegetarisch',
            }
            content = json.dumps([{'en': 'Vegan', 'de': 'Vegan'}]).encode()

            def competing_upload():
                """Submit a competing request on its own database connection."""
                try:
                    client = self.client.__class__()
                    client.force_login(self.user)
                    with connections['default'].cursor() as cursor:
                        cursor.execute("SET lock_timeout = '500ms'")
                    try:
                        return client.post(
                            question.urls.edit,
                            {
                                **data,
                                'options': SimpleUploadedFile('options.json', content),
                            },
                        ).status_code
                    except OperationalError as error:
                        return error.__cause__.sqlstate
                finally:
                    connections.close_all()

            with transaction.atomic():
                response = self.client.post(
                    question.urls.edit,
                    {
                        **data,
                        'options': SimpleUploadedFile('options.json', content),
                    },
                )
                assert response.status_code == 302
                with ThreadPoolExecutor(max_workers=1) as executor:
                    assert executor.submit(competing_upload).result(timeout=30) == '55P03'

            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(competing_upload).result(timeout=30) == 302
            assert question.options.count() == 2
            assert question.options.filter(pk=existing.pk).exists()
