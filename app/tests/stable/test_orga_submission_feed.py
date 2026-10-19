import pytest
from django_scopes import scope

from eventyay.base.models import Submission, SubmissionType, Team


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
