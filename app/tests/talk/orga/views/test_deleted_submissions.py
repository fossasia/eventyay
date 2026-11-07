import html
import re
from urllib.parse import quote

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


def _create(event, state, **kwargs):
    return Submission.objects.create(event=event, submission_type=event.submission_types.first(), state=state, **kwargs)


def _hrefs(text, prefix):
    return {html.unescape(href) for href in re.findall(r'href="([^"]+)"', text) if href.startswith(prefix)}


@pytest.fixture
def deleted_submission(submission):
    with scope(event=submission.event):
        submission.remove(force=True)
    return submission


@pytest.mark.django_db
def test_remove_marks_deleted_and_preserves_answers(submission, question):
    with scope(event=submission.event):
        answer = Answer.objects.create(submission=submission, question=question, answer='Test answer data')
        submission.remove()
        submission.refresh_from_db()
        assert submission.state == SubmissionStates.DELETED
        assert submission.is_deleted is True
        assert submission.answers.filter(pk=answer.pk).exists()


@pytest.mark.django_db
def test_list_hides_deleted_unless_filtered(orga_client, event, submission):
    with scope(event=event):
        deleted = _create(event, SubmissionStates.DELETED, title='Deleted Proposal Title')
        state_choices = dict(SubmissionFilterForm(event=event).fields['state'].choices)
        choices = list(state_choices)
    assert SubmissionStates.DELETED in choices and SubmissionStates.DRAFT not in choices
    assert str(state_choices[SubmissionStates.REJECTED]) == 'Not accepted'

    for query, visible in [
        ('', {submission}),
        ('?state=deleted', {deleted}),
        ('?state=deleted&state=submitted', {submission, deleted}),
    ]:
        response = orga_client.get(event.orga_urls.submissions + query)
        assert response.status_code == 200
        for sub in (submission, deleted):
            assert (sub.title in response.text) == (sub in visible), (query, sub.title)


@pytest.mark.django_db
def test_counts_exclude_deleted(event, speaker, submission, track):
    with scope(event=event):
        tag = event.tags.create(tag='Test Tag', color='#ff0000')
        submission.tags.add(tag)
        submission.track = track
        submission.save()
        # The track filter is only shown once an event has several tracks
        event.tracks.create(name='Track 2', color='#00ff00')
        deleted = _create(event, SubmissionStates.DELETED, track=track, title='Deleted Tagged')
        deleted.tags.add(tag)
        deleted.speakers.add(speaker)

        assert deleted not in speaker.profiles.get(event=event).submissions
        speaker_form = UserSpeakerFilterForm(events=Event.objects.filter(pk=event.pk), data={'role': 'submitter'})
        assert speaker_form.is_valid()
        assert speaker_form.filter_queryset(User.objects.filter(pk=speaker.pk)).get().submission_count == 1

        filter_form = SubmissionFilterForm(event=event)
        assert filter_form.fields['tags'].queryset.get(pk=tag.pk).submission_count == 1
        assert filter_form.fields['track'].queryset.get(pk=track.pk).count == 1


@pytest.mark.django_db
def test_question_missing_answers(event, speaker, submission):
    with scope(event=event):
        deleted = _create(event, SubmissionStates.DELETED, title='Deleted Proposal')
        deleted_speaker = User.objects.create(email='deleted_spk@example.com')
        deleted.speakers.add(deleted_speaker)

        sub_q = TalkQuestion.objects.create(event=event, question='Sub Q?', target=TalkQuestionTarget.SUBMISSION)
        assert sub_q.missing_answers() == 1
        assert sub_q.missing_answers(filter_talks=[deleted]) == 0
        assert sub_q.missing_answers(filter_talks=[submission, deleted]) == 1
        assert sub_q.missing_answers(filter_talks=(s for s in [submission, deleted])) == 1
        assert sub_q.missing_answers(filter_talks=Submission.all_objects.filter(event=event)) == 1
        assert sub_q.missing_answers(filter_talks=[]) == 0
        assert sub_q.missing_answers(filter_talks=submission) == 1
        assert sub_q.missing_answers(filter_talks=submission.pk) == 1
        # Several answers for the same talk count once
        Answer.objects.create(question=sub_q, submission=submission, answer='A1')
        Answer.objects.create(question=sub_q, submission=submission, answer='A2')
        assert sub_q.missing_answers() == 0
        assert sub_q.missing_answers(filter_talks=[submission]) == 0

        # Track limits exclude non-matching submissions
        limited_q = TalkQuestion.objects.create(
            event=event, question='Limited Q?', target=TalkQuestionTarget.SUBMISSION
        )
        limited_q.tracks.add(event.tracks.create(name='Track A', color='#ff0000'))
        assert limited_q.missing_answers() == 0
        submission.track = limited_q.tracks.get()
        submission.save()
        assert limited_q.missing_answers() == 1

        # Track limits also apply to speaker questions
        limited_spk_q = TalkQuestion.objects.create(
            event=event, question='Limited Spk Q?', target=TalkQuestionTarget.SPEAKER
        )
        limited_spk_q.tracks.add(event.tracks.create(name='Track B', color='#00ff00'))
        assert limited_spk_q.missing_answers() == 0
        limited_spk_q.tracks.add(submission.track)
        assert limited_spk_q.missing_answers() == 1

        spk_q = TalkQuestion.objects.create(event=event, question='Spk Q?', target=TalkQuestionTarget.SPEAKER)
        assert spk_q.missing_answers() == 1
        assert spk_q.missing_answers(filter_speakers=[deleted_speaker]) == 0
        assert spk_q.missing_answers(filter_speakers=[speaker, deleted_speaker]) == 1
        assert spk_q.missing_answers(filter_speakers=[speaker.pk, deleted_speaker.pk]) == 1
        assert spk_q.missing_answers(filter_speakers=User.objects.filter(pk__in=[speaker.pk, deleted_speaker.pk])) == 1
        assert spk_q.missing_answers(filter_speakers=[]) == 0
        assert spk_q.missing_answers(filter_speakers=speaker) == 1
        assert spk_q.missing_answers(filter_speakers=speaker.pk) == 1
        Answer.objects.create(question=spk_q, person=speaker, answer='A1')
        Answer.objects.create(question=spk_q, person=speaker, answer='A2')
        assert spk_q.missing_answers() == 0
        assert spk_q.missing_answers(filter_speakers=[speaker]) == 0


@pytest.mark.django_db
def test_build_data_excludes_deleted_submission_with_released_slot(slot):
    with scope(event=slot.schedule.event):
        schedule, submission = slot.schedule, slot.submission
        assert submission.code in {talk.get('code') for talk in schedule.build_data()['talks']}

        submission.remove()
        slot.refresh_from_db()
        assert slot.schedule == schedule and slot.is_visible is True
        assert submission.code not in {talk.get('code') for talk in schedule.build_data()['talks']}


@pytest.mark.django_db
def test_reviewer_track_limits_apply_to_deleted_submissions(review_client, review_user, event, track, other_track):
    with scope(event=event):
        review_user.teams.first().limit_tracks.add(track)
        submissions = {
            (allowed, state): _create(event, state, track=track if allowed else other_track)
            for allowed in (True, False)
            for state in (SubmissionStates.SUBMITTED, SubmissionStates.DELETED)
        }

    for (allowed, state), sub in submissions.items():
        for page in ('base', 'speakers', 'reviews', 'comments'):
            status = review_client.get(getattr(sub.orga_urls, page), follow=True).status_code
            assert status == (200 if allowed else 404), (allowed, state, page)
        # Reviewers cannot change the state, so they cannot restore deleted sessions either
        assert review_client.get(sub.orga_urls.accept).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('action', 'target'),
    [
        ('make_submitted', SubmissionStates.SUBMITTED),
        ('accept', SubmissionStates.ACCEPTED),
        ('reject', SubmissionStates.REJECTED),
        ('confirm', SubmissionStates.CONFIRMED),
        ('cancel', SubmissionStates.CANCELED),
        ('withdraw', SubmissionStates.WITHDRAWN),
    ],
)
def test_change_state_of_deleted_submission_from_filtered_list(orga_client, event, deleted_submission, action, target):
    # Use the state dropdown link of the deleted session in the "Deleted" filter
    res_list = orga_client.get(f'{event.orga_urls.submissions}?state=deleted')
    (dropdown_link,) = _hrefs(res_list.text, f'{getattr(deleted_submission.orga_urls, action)}?')
    assert orga_client.get(dropdown_link).status_code == 200

    assert orga_client.post(dropdown_link, follow=True).status_code == 200
    with scope(event=event):
        deleted_submission.refresh_from_db()
        assert deleted_submission.state == target
    assert deleted_submission.title in orga_client.get(event.orga_urls.submissions).text


@pytest.mark.django_db
def test_apply_pending_state_on_deleted_submission(orga_client, event, deleted_submission):
    assert orga_client.post(deleted_submission.orga_urls.accept, {'pending': 'on'}).status_code == 302
    with scope(event=event):
        deleted_submission.refresh_from_db()
        assert (deleted_submission.state, deleted_submission.pending_state) == ('deleted', 'accepted')

    assert orga_client.post(deleted_submission.orga_urls.apply_pending).status_code == 302
    with scope(event=event):
        deleted_submission.refresh_from_db()
        assert (deleted_submission.state, deleted_submission.pending_state) == ('accepted', None)


@pytest.mark.django_db
def test_deleted_submission_pages_have_no_broken_links(orga_client, event, deleted_submission):
    urls = deleted_submission.orga_urls
    links = set()
    for page in (urls.base, urls.speakers, urls.reviews, urls.comments, urls.history):
        response = orga_client.get(page)
        assert response.status_code == 200, page
        links |= {link.split('?')[0] for link in _hrefs(response.text, urls.base)}
    assert urls.edit not in links

    row_links = _hrefs(orga_client.get(f'{event.orga_urls.submissions}?state=deleted').text, urls.base)
    assert row_links
    assert not any(link.startswith((urls.edit, urls.delete)) for link in row_links)
    for link in links | row_links:
        assert orga_client.get(link).status_code == 200, link


@pytest.mark.django_db
def test_deleted_submission_content_changes_stay_blocked(orga_client, event, deleted_submission):
    urls = deleted_submission.orga_urls
    with scope(event=event):
        speaker_count = deleted_submission.speakers.count()

    assert orga_client.get(urls.edit).status_code == 404
    assert orga_client.post(urls.edit, {'title': 'Changed'}).status_code == 404
    assert orga_client.post(urls.speakers, {'email': 'new@example.com'}).status_code == 404
    assert orga_client.post(urls.toggle_featured).status_code == 404
    with scope(event=event):
        deleted_submission.refresh_from_db()
        assert deleted_submission.title != 'Changed'
        assert deleted_submission.speakers.count() == speaker_count
        assert not deleted_submission.speaker_invitations.filter(email='new@example.com').exists()
        assert deleted_submission.is_featured is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('start_state', 'action', 'other_state', 'query', 'expected_query'),
    [
        ('deleted', 'make_submitted', None, 'state=deleted', ''),
        ('deleted', 'make_submitted', 'deleted', 'state=deleted', 'state=deleted'),
        ('deleted', 'make_submitted', None, 'state=deleted&state=submitted', 'state=deleted&state=submitted'),
        ('submitted', 'accept', None, 'state=submitted', ''),
        ('submitted', 'accept', 'submitted', 'state=submitted', 'state=submitted'),
        ('submitted', 'accept', None, 'q=nothing-matches', 'q=nothing-matches'),
    ],
)
def test_emptied_state_filter_returns_to_full_list(
    orga_client, event, submission, start_state, action, other_state, query, expected_query
):
    with scope(event=event):
        if start_state == SubmissionStates.DELETED:
            submission.remove(force=True)
        if other_state:
            _create(event, other_state, title='Other session')

    url = f'{getattr(submission.orga_urls, action)}?next={quote(f"{event.orga_urls.submissions}?{query}")}'
    response = orga_client.post(url)
    assert response.status_code == 302
    assert response.url == event.orga_urls.submissions + (f'?{expected_query}' if expected_query else '')
