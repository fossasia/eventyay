import pytest
from django_scopes import scope

from eventyay.base.models import Submission, SubmissionType, Team, Track


@pytest.fixture
def submission(event):
    with scope(event=event):
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        return Submission.objects.create(
            title='A proposal nobody outside the team should see',
            event=event,
            submission_type=submission_type,
            abstract='Abstract',
            content_locale='en',
        )


@pytest.fixture
def talk_team(organizer, user):
    team = Team.objects.create(
        organizer=organizer,
        name='Program committee',
        all_events=True,
        can_change_submissions=True,
    )
    team.members.add(user)
    return team


@pytest.mark.django_db
def test_feed_lists_proposals_for_team_member(client, user, talk_team, submission):
    client.force_login(user)

    response = client.get(submission.event.orga_urls.submission_feed)

    assert response.status_code == 200
    assert submission.title in response.text
    assert '<summary' not in response.text
    assert f'state={submission.state}' not in response.text
    assert submission.state not in response.text


@pytest.mark.django_db
def test_feed_only_lists_tracks_the_team_is_limited_to(
    client, user, event, talk_team, submission
):
    with scope(event=event):
        own_track = Track.objects.create(event=event, name='Own track')
        other_track = Track.objects.create(event=event, name='Other track')
        talk_team.limit_tracks.add(own_track)
        own = Submission.objects.create(
            title='Proposal in the own track',
            event=event,
            submission_type=submission.submission_type,
            track=own_track,
            content_locale='en',
        )
        submission.track = other_track
        submission.save()
    client.force_login(user)

    response = client.get(event.orga_urls.submission_feed)

    assert response.status_code == 200
    assert own.title in response.text
    assert submission.title not in response.text


@pytest.mark.django_db
def test_feed_is_404_for_user_without_team(authenticated_client, submission):
    response = authenticated_client.get(submission.event.orga_urls.submission_feed)

    assert response.status_code == 404
    assert submission.title not in response.text


@pytest.mark.django_db
def test_feed_is_404_for_team_member_without_submission_permission(
    organizer_client, submission
):
    # The shared team fixture has ticketing permissions only.
    response = organizer_client.get(submission.event.orga_urls.submission_feed)

    assert response.status_code == 404
    assert submission.title not in response.text


@pytest.mark.django_db
def test_feed_redirects_anonymous_user_to_login(client, submission):
    response = client.get(submission.event.orga_urls.submission_feed)

    assert response.status_code == 302
    assert '/login/' in response['Location']


@pytest.mark.django_db
def test_feed_only_lists_proposals_a_reviewer_may_see(
    client, user, organizer, event, submission
):
    team = Team.objects.create(
        organizer=organizer,
        name='Reviewers',
        all_events=True,
        is_reviewer=True,
    )
    team.members.add(user)
    with scope(event=event):
        own_track = Track.objects.create(event=event, name='Own track')
        other_track = Track.objects.create(event=event, name='Other track')
        team.limit_tracks.add(own_track)
        visible = Submission.objects.create(
            title='Proposal the reviewer may review',
            event=event,
            submission_type=submission.submission_type,
            track=own_track,
            content_locale='en',
        )
        own_proposal = Submission.objects.create(
            title='Proposal the reviewer is speaking in',
            event=event,
            submission_type=submission.submission_type,
            track=own_track,
            content_locale='en',
        )
        own_proposal.speakers.add(user)
        submission.track = other_track
        submission.save()
    client.force_login(user)

    response = client.get(event.orga_urls.submission_feed)

    assert response.status_code == 200
    assert visible.title in response.text
    assert own_proposal.title not in response.text
    assert submission.title not in response.text
