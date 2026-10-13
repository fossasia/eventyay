import pytest
from django_scopes import scope

from eventyay.base.models import (
    Answer,
    Event,
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
        submission.remove()
        submission.refresh_from_db()
        assert submission.state == SubmissionStates.DELETED
        assert submission.is_deleted is True
        assert submission.answers.filter(pk=answer.pk).exists()


@pytest.mark.django_db
def test_submission_list_view_filters_deleted(orga_client, event, submission, submission_type):
    with scope(event=event):
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal Title",
            state=SubmissionStates.DELETED,
        )

    # Default list excludes deleted
    res_default = orga_client.get(event.orga_urls.submissions, follow=True)
    assert res_default.status_code == 200
    assert submission.title in res_default.text and deleted_sub.title not in res_default.text

    # Filtered by DELETED state includes only deleted
    res_deleted = orga_client.get(f"{event.orga_urls.submissions}?state={SubmissionStates.DELETED}", follow=True)
    assert res_deleted.status_code == 200
    assert deleted_sub.title in res_deleted.text and submission.title not in res_deleted.text


@pytest.mark.django_db
def test_submission_filter_form(event, submission, submission_type):
    with scope(event=event):
        deleted = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal",
            state=SubmissionStates.DELETED,
        )
        form = SubmissionFilterForm(event=event)
        choices = [c[0] for c in form.fields["state"].choices]
        assert SubmissionStates.DELETED in choices and SubmissionStates.DRAFT not in choices

        base_qs = event.submissions(manager="all_objects").exclude(state=SubmissionStates.DRAFT)
        # Default: excludes deleted
        f_default = SubmissionFilterForm(event=event, data={})
        assert f_default.is_valid()
        assert deleted not in f_default.filter_queryset(base_qs)
        # Filter DELETED: includes only deleted
        f_del = SubmissionFilterForm(event=event, data={"state": [SubmissionStates.DELETED]})
        assert f_del.is_valid()
        qs_del = f_del.filter_queryset(base_qs)
        assert submission not in qs_del and deleted in qs_del
        # Filter both: includes both
        f_both = SubmissionFilterForm(
            event=event, data={"state": [SubmissionStates.SUBMITTED, SubmissionStates.DELETED]}
        )
        assert f_both.is_valid()
        qs_both = f_both.filter_queryset(base_qs)
        assert submission in qs_both and deleted in qs_both


@pytest.mark.django_db
def test_speaker_submissions_and_filter_form_exclude_deleted(event, speaker, submission, submission_type):
    with scope(event=event):
        deleted = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Speaker Sub",
            state=SubmissionStates.DELETED,
        )
        deleted.speakers.add(speaker)

        # Profile.submissions property excludes deleted
        assert deleted not in speaker.profiles.get(event=event).submissions

        # UserSpeakerFilterForm excludes deleted from submission_count
        form = UserSpeakerFilterForm(events=Event.objects.filter(pk=event.pk), data={"role": "submitter"})
        assert form.is_valid()
        speaker_res = form.filter_queryset(User.objects.filter(pk=speaker.pk)).first()
        assert speaker_res is not None
        assert speaker_res.submission_count == 1


@pytest.mark.django_db
def test_submission_filter_form_counts_exclude_deleted(event, submission, submission_type, track):
    with scope(event=event):
        tag = event.tags.create(tag="Test Tag", color="#ff0000")
        submission.tags.add(tag)
        submission.track = track
        submission.save()
        event.tracks.create(name="Track 2", color="#00ff00")

        deleted = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            track=track,
            title="Deleted Tagged",
            state=SubmissionStates.DELETED,
        )
        deleted.tags.add(tag)

        form = SubmissionFilterForm(event=event)
        assert form.fields["tags"].queryset.get(pk=tag.pk).submission_count == 1
        assert form.fields["track"].queryset.get(pk=track.pk).count == 1


@pytest.mark.django_db
def test_question_missing_answers(event, speaker, submission):
    with scope(event=event):
        deleted_sub = Submission.objects.create(
            event=event,
            submission_type=submission.submission_type,
            title="Deleted Proposal",
            state=SubmissionStates.DELETED,
        )
        deleted_spk = User.objects.create(email="deleted_spk@example.com")
        deleted_sub.speakers.add(deleted_spk)

        # 1. Submission-targeted question
        sub_q = TalkQuestion.objects.create(event=event, question="Sub Q?", target=TalkQuestionTarget.SUBMISSION)
        assert sub_q.missing_answers() == 1
        assert sub_q.missing_answers(filter_talks=[deleted_sub]) == 0
        assert sub_q.missing_answers(filter_talks=[submission, deleted_sub]) == 1
        assert sub_q.missing_answers(filter_talks=Submission.all_objects.filter(event=event)) == 1
        assert sub_q.missing_answers(filter_talks=[]) == 0

        # Answer submission question (multiple answers for same talk count once)
        Answer.objects.create(question=sub_q, submission=submission, answer="A1")
        Answer.objects.create(question=sub_q, submission=submission, answer="A2")
        assert sub_q.missing_answers() == 0
        assert sub_q.missing_answers(filter_talks=[submission]) == 0

        # Track and submission_type limits exclude non-matching submissions
        track = event.tracks.create(name="Track A", color="#ff0000")
        sub_q_limited = TalkQuestion.objects.create(
            event=event, question="Limited Q?", target=TalkQuestionTarget.SUBMISSION
        )
        sub_q_limited.tracks.add(track)
        assert sub_q_limited.missing_answers() == 0
        submission.track = track
        submission.save()
        assert sub_q_limited.missing_answers() == 1

        # 2. Speaker-targeted question
        spk_q = TalkQuestion.objects.create(event=event, question="Spk Q?", target=TalkQuestionTarget.SPEAKER)
        assert spk_q.missing_answers() == 1
        assert spk_q.missing_answers(filter_speakers=[deleted_spk]) == 0
        assert spk_q.missing_answers(filter_speakers=[speaker, deleted_spk]) == 1
        assert spk_q.missing_answers(filter_speakers=User.objects.filter(pk__in=[speaker.pk, deleted_spk.pk])) == 1
        assert spk_q.missing_answers(filter_speakers=[]) == 0

        # Answer speaker question
        Answer.objects.create(question=spk_q, person=speaker, answer="A1")
        Answer.objects.create(question=spk_q, person=speaker, answer="A2")
        assert spk_q.missing_answers() == 0
        assert spk_q.missing_answers(filter_speakers=[speaker]) == 0


@pytest.mark.django_db
def test_deleted_submission_read_only_allowed_but_edit_blocked(orga_client, event, submission_type):
    with scope(event=event):
        deleted = Submission.objects.create(
            event=event,
            submission_type=submission_type,
            title="Deleted Proposal",
            state=SubmissionStates.DELETED,
        )
    assert orga_client.get(deleted.orga_urls.base, follow=True).status_code == 200
    assert orga_client.get(deleted.orga_urls.edit, follow=True).status_code == 404


@pytest.mark.django_db
def test_reviewer_track_limit_detail_view(review_client, review_user, event, track, other_track, submission_type):
    with scope(event=event):
        review_user.teams.first().limit_tracks.add(track)
        allowed_sub = Submission.objects.create(
            event=event, submission_type=submission_type, track=track, state=SubmissionStates.SUBMITTED
        )
        allowed_deleted = Submission.objects.create(
            event=event, submission_type=submission_type, track=track, state=SubmissionStates.DELETED
        )
        off_sub = Submission.objects.create(
            event=event, submission_type=submission_type, track=other_track, state=SubmissionStates.SUBMITTED
        )
        off_deleted = Submission.objects.create(
            event=event, submission_type=submission_type, track=other_track, state=SubmissionStates.DELETED
        )

    assert review_client.get(allowed_sub.orga_urls.base, follow=True).status_code == 200
    assert review_client.get(allowed_deleted.orga_urls.base, follow=True).status_code == 200
    assert review_client.get(off_sub.orga_urls.base, follow=True).status_code == 404
    assert review_client.get(off_deleted.orga_urls.base, follow=True).status_code == 404


@pytest.mark.django_db
def test_build_data_excludes_deleted_submission_with_released_slot(slot):
    with scope(event=slot.schedule.event):
        schedule = slot.schedule
        submission = slot.submission

        assert any(talk.get("code") == submission.code for talk in schedule.build_data()["talks"])

        submission.remove()
        submission.refresh_from_db()
        slot.refresh_from_db()
        assert submission.state == SubmissionStates.DELETED
        assert slot.schedule == schedule and slot.is_visible is True

        talk_codes = {talk.get("code") for talk in schedule.build_data()["talks"] if talk.get("code")}
        assert submission.code not in talk_codes
