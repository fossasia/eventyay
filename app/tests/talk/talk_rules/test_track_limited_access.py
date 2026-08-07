import json

import pytest
from django_scopes import scope

from eventyay.talk_rules.submission import has_reviewer_access, submissions_for_user


@pytest.mark.django_db
def test_has_reviewer_access_respects_track_limits(
    review_user, submission, other_submission, track, other_track
):
    with scope(event=submission.event):
        submission.track = track
        submission.save()
        other_submission.track = other_track
        other_submission.save()
        review_user.teams.first().limit_tracks.add(track)

        assert has_reviewer_access(review_user, submission)
        assert not has_reviewer_access(review_user, other_submission)


@pytest.mark.django_db
def test_assigned_reviewer_must_match_track_limits(
    review_user, submission, other_submission, track, other_track
):
    with scope(event=submission.event):
        phase = submission.event.active_review_phase
        phase.proposal_visibility = 'assigned'
        phase.save()
        submission.track = other_track
        submission.save()
        other_submission.track = track
        other_submission.save()
        review_user.teams.first().limit_tracks.add(track)
        submission.assigned_reviewers.add(review_user)
        other_submission.assigned_reviewers.add(review_user)

        assert not has_reviewer_access(review_user, submission)
        assert has_reviewer_access(review_user, other_submission)


@pytest.mark.django_db
def test_submissions_for_user_filters_manager_by_track(
    orga_user, event, submission, other_submission, track, other_track
):
    with scope(event=event):
        team = orga_user.teams.first()
        team.limit_tracks.add(track)
        submission.track = track
        submission.save()
        other_submission.track = other_track
        other_submission.save()

        visible = submissions_for_user(event, orga_user)
        assert submission in visible
        assert other_submission not in visible


@pytest.mark.django_db
def test_reviewer_cannot_open_other_track_submission(
    review_client, review_user, submission, other_submission, track, other_track
):
    with scope(event=submission.event):
        submission.track = track
        submission.save()
        other_submission.track = other_track
        other_submission.save()
        review_user.teams.first().limit_tracks.add(track)

    response = review_client.get(other_submission.orga_urls.base, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_reviewer_api_hides_speakers_when_team_force_hide(
    client, review_user_token, review_user, submission, event
):
    with scope(event=event):
        review_user.teams.first().force_hide_speaker_names = True
        review_user.teams.first().save()
        assert event.active_review_phase.can_see_speaker_names is True

    response = client.get(
        event.api_urls.submissions,
        follow=True,
        headers={'Authorization': f'Token {review_user_token.token}'},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    submission_result = next(item for item in content['results'] if item['code'] == submission.code)
    assert submission_result['speakers'] == []


@pytest.mark.django_db
def test_reviewer_api_hides_expanded_speakers_when_team_force_hide(
    client, review_user_token, review_user, submission, event
):
    with scope(event=event):
        review_user.teams.first().force_hide_speaker_names = True
        review_user.teams.first().save()
        assert event.active_review_phase.can_see_speaker_names is True

    response = client.get(
        event.api_urls.submissions + '?expand=speakers',
        follow=True,
        headers={'Authorization': f'Token {review_user_token.token}'},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    submission_result = next(item for item in content['results'] if item['code'] == submission.code)
    assert submission_result['speakers'] == []


@pytest.mark.django_db
def test_reviewer_api_still_blocked_in_anonymised_phase(
    client, review_user_token, submission, event
):
    with scope(event=event):
        event.active_review_phase.can_see_speaker_names = False
        event.active_review_phase.save()

    response = client.get(
        event.api_urls.submissions,
        follow=True,
        headers={'Authorization': f'Token {review_user_token.token}'},
    )
    assert response.status_code == 403
