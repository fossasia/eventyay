import pytest
from django_scopes import scope

from eventyay.base.models import (
    Answer,
    Event,
    Organizer,
    Submission,
    SubmissionStates,
    TalkQuestion,
    TalkQuestionTarget,
    User,
)
from eventyay.person.forms.profile import UserSpeakerFilterForm
from eventyay.submission.forms.submission import SubmissionFilterForm


@pytest.mark.django_db
def test_submission_delete_state_transition(submission):
    with scope(event=submission.event):
        assert submission.state == SubmissionStates.SUBMITTED
        submission.state = SubmissionStates.DELETED
        submission.save()
        submission.refresh_from_db()
        assert submission.state == SubmissionStates.DELETED
        assert submission.is_deleted is True


@pytest.mark.django_db
def test_submission_remove_preserves_answers(submission, question):
    with scope(event=submission.event):
        answer = Answer.objects.create(
            submission=submission,
            question=question,
            answer="Test answer data",
        )
        assert submission.answers.count() == 1
        # Calling remove() soft-deletes the submission and preserves session data
        submission.remove()
        submission.refresh_from_db()
        assert submission.state == SubmissionStates.DELETED
        assert submission.is_deleted is True
        # Answers remain preserved in the database
        assert submission.answers.count() == 1
        assert Answer.objects.filter(pk=answer.pk).exists()


@pytest.mark.django_db
def test_default_submission_list_excludes_deleted(orga_client, event, submission, submission_type):
    with scope(event=event):
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal Title",
            state=SubmissionStates.DELETED,
        )
        assert Submission.all_objects.filter(event=event).count() == 2

    response = orga_client.get(event.orga_urls.submissions, follow=True)
    assert response.status_code == 200
    assert submission.title in response.text
    assert deleted_sub.title not in response.text


@pytest.mark.django_db
def test_submission_list_filtered_by_deleted_state(orga_client, event, submission, submission_type):
    with scope(event=event):
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Unique Proposal Title",
            state=SubmissionStates.DELETED,
        )

    response = orga_client.get(
        event.orga_urls.submissions + f"?state={SubmissionStates.DELETED}",
        follow=True,
    )
    assert response.status_code == 200
    assert deleted_sub.title in response.text
    assert submission.title not in response.text


@pytest.mark.django_db
def test_submission_filter_form_includes_deleted_choice(event):
    with scope(event=event):
        form = SubmissionFilterForm(event=event)
        choices = [c[0] for c in form.fields["state"].choices]
        assert SubmissionStates.DELETED in choices
        assert SubmissionStates.DRAFT not in choices


@pytest.mark.django_db
def test_submission_filter_form_queryset_filtering(event, submission, submission_type):
    with scope(event=event):
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal",
            state=SubmissionStates.DELETED,
        )
        base_qs = event.submissions(manager="all_objects").exclude(state=SubmissionStates.DRAFT)

        # Default filtering (no state specified)
        form = SubmissionFilterForm(event=event, data={})
        assert form.is_valid()
        qs = form.filter_queryset(base_qs)
        assert submission in qs
        assert deleted_sub not in qs

        # Filter for DELETED only
        form_deleted = SubmissionFilterForm(event=event, data={"state": [SubmissionStates.DELETED]})
        assert form_deleted.is_valid()
        qs_deleted = form_deleted.filter_queryset(base_qs)
        assert submission not in qs_deleted
        assert deleted_sub in qs_deleted

        # Filter for SUBMITTED and DELETED
        form_both = SubmissionFilterForm(
            event=event,
            data={"state": [SubmissionStates.SUBMITTED, SubmissionStates.DELETED]},
        )
        assert form_both.is_valid()
        qs_both = form_both.filter_queryset(base_qs)
        assert submission in qs_both
        assert deleted_sub in qs_both


@pytest.mark.django_db
def test_speaker_profile_submissions_excludes_deleted(event, speaker, submission, submission_type):
    with scope(event=event):
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal By Speaker",
            state=SubmissionStates.DELETED,
        )
        deleted_sub.speakers.add(speaker)
        profile = speaker.profiles.get(event=event)
        assert deleted_sub not in profile.submissions
        assert submission in profile.submissions


@pytest.mark.django_db
def test_user_speaker_filter_form_excludes_deleted(event, speaker, submission, submission_type):
    with scope(event=event):
        # Add a deleted submission for the same speaker in this event
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal By Speaker",
            state=SubmissionStates.DELETED,
        )
        deleted_sub.speakers.add(speaker)

        form = UserSpeakerFilterForm(events=Event.objects.filter(pk=event.pk), data={"role": "submitter"})
        assert form.is_valid()
        qs = form.filter_queryset(User.objects.filter(pk=speaker.pk))
        speaker_result = qs.first()
        assert speaker_result is not None
        # Must accurately count only the 1 non-deleted submission
        assert speaker_result.submission_count == 1



@pytest.mark.django_db
def test_tag_submission_count_excludes_deleted(event, submission, submission_type):
    with scope(event=event):
        tag = event.tags.create(tag="Test Tag", color="#ff0000")
        submission.tags.add(tag)
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal Tagged",
            state=SubmissionStates.DELETED,
        )
        deleted_sub.tags.add(tag)

        form = SubmissionFilterForm(event=event)
        tag_choice = form.fields["tags"].queryset.get(pk=tag.pk)
        # Should only count the non-deleted submission
        assert tag_choice.submission_count == 1


@pytest.mark.django_db
def test_track_submission_count_excludes_deleted(event, submission, submission_type, track):
    with scope(event=event):
        submission.track = track
        submission.save()
        # Create a second track so track filter is rendered
        event.tracks.create(name="Track 2", color="#00ff00")
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            track=track,
            title="Deleted Proposal on Track",
            state=SubmissionStates.DELETED,
        )

        form = SubmissionFilterForm(event=event)
        track_choice = form.fields["track"].queryset.get(pk=track.pk)
        assert track_choice.count == 1


@pytest.mark.django_db
def test_question_missing_answers_excludes_deleted(event, speaker, submission, submission_type):
    with scope(event=event):
        # 1. Submission-targeted question
        sub_question = TalkQuestion.objects.create(
            event=event,
            question="Submission Question?",
            target=TalkQuestionTarget.SUBMISSION,
        )
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal",
            state=SubmissionStates.DELETED,
        )
        # Only active submission needs answer
        assert sub_question.missing_answers() == 1
        Answer.objects.create(
            submission=submission,
            question=sub_question,
            answer="Done",
        )
        assert sub_question.missing_answers() == 0

        # 2. Speaker-targeted question
        speaker_question = TalkQuestion.objects.create(
            event=event,
            question="Speaker Question?",
            target=TalkQuestionTarget.SPEAKER,
        )
        # Only eligible speakers with active proposals count
        assert speaker_question.missing_answers() == 1
        Answer.objects.create(
            person=speaker,
            question=speaker_question,
            answer="Done",
        )
        assert speaker_question.missing_answers() == 0


@pytest.mark.django_db
def test_question_missing_answers_supports_list_input(event, speaker, submission):
    with scope(event=event):
        sub_question = TalkQuestion.objects.create(
            event=event,
            question="Submission Question?",
            target=TalkQuestionTarget.SUBMISSION,
        )
        # Pass Python list directly
        assert sub_question.missing_answers(filter_talks=[submission]) == 1

        speaker_question = TalkQuestion.objects.create(
            event=event,
            question="Speaker Question?",
            target=TalkQuestionTarget.SPEAKER,
        )
        # Pass Python list directly
        assert speaker_question.missing_answers(filter_speakers=[speaker]) == 1


@pytest.mark.django_db
def test_deleted_submission_read_only_allowed_but_edit_blocked(orga_client, event, submission_type):
    with scope(event=event):
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal",
            state=SubmissionStates.DELETED,
        )

    # Read-only detail view allows viewing deleted submission
    response_view = orga_client.get(deleted_sub.orga_urls.base, follow=True)
    assert response_view.status_code == 200

    # Edit view (mutation) blocks deleted submission and returns 404
    response_edit = orga_client.get(deleted_sub.orga_urls.edit, follow=True)
    assert response_edit.status_code == 404

