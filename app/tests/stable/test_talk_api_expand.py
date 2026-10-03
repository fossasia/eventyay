import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django_scopes import scope

from eventyay.base.models import Answer, TalkQuestion, TalkQuestionTarget, TalkQuestionVariant, User
from eventyay.base.models.profile import SpeakerProfile
from eventyay.base.models.review import Review
from eventyay.base.models.submission import Submission


@pytest.fixture
def speaker(db):
    return User.objects.create_user(
        email='speaker@example.com',
        password='speakerpass123',
        fullname='Jane Speaker',
        locale='en',
    )


@pytest.fixture
def submission(event, speaker):
    with scope(event=event):
        submission = Submission.objects.create(
            title='A talk', event=event, submission_type=event.cfp.default_type
        )
        submission.speakers.add(speaker)
        SpeakerProfile.objects.get_or_create(user=speaker, event=event)
        return submission


@pytest.fixture
def talk_team(team):
    team.can_change_submissions = True
    team.is_reviewer = True
    team.save()
    return team


@pytest.mark.django_db
def test_reviews_expand_user(organizer_client, talk_team, user, event, submission):
    with scope(event=event):
        review = Review.objects.create(submission=submission, user=user, text='Good talk')

    resp = organizer_client.get(
        f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/reviews/?expand=user'
    )

    assert resp.status_code == 200
    result = resp.json()['results'][0]
    assert result['id'] == review.pk
    assert result['user'] == {'code': user.code, 'fullname': 'Test User', 'email': user.email}


@pytest.mark.django_db
def test_answers_expand_person(organizer_client, talk_team, event, submission, speaker):
    with scope(event=event):
        question = TalkQuestion.objects.create(
            question='Shirt size?',
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SPEAKER,
            event=event,
        )
        answer = Answer.objects.create(question=question, person=speaker, answer='M')

    url = f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/answers/'

    resp = organizer_client.get(url)
    assert resp.status_code == 200
    assert resp.json()['results'][0]['person'] == speaker.code

    resp = organizer_client.get(url + '?expand=person')
    assert resp.status_code == 200
    result = resp.json()['results'][0]
    assert result['id'] == answer.pk
    assert result['person']['code'] == speaker.code
    assert result['person']['fullname'] == 'Jane Speaker'
    assert 'answers' not in result['person']


@pytest.mark.django_db
def test_answers_expand_person_query_count(organizer_client, talk_team, event, submission, speaker):
    url = f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/answers/?expand=person'
    with scope(event=event):
        question = TalkQuestion.objects.create(
            question='Shirt size?',
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SPEAKER,
            event=event,
        )
        Answer.objects.create(question=question, person=speaker, answer='M')

    with CaptureQueriesContext(connection) as one_answer:
        assert organizer_client.get(url).status_code == 200

    with scope(event=event):
        for i in range(3):
            person = User.objects.create_user(email=f'speaker{i}@example.com', password='x', fullname=f'Speaker {i}')
            submission.speakers.add(person)
            SpeakerProfile.objects.create(user=person, event=event)
            Answer.objects.create(question=question, person=person, answer='L')

    with CaptureQueriesContext(connection) as four_answers:
        resp = organizer_client.get(url)
    assert resp.status_code == 200
    assert len(resp.json()['results']) == 4

    def lookups(ctx):
        # Profile and user loads must not repeat per answer
        return [
            q['sql'] for q in ctx.captured_queries
            if 'FROM "base_speakerprofile"' in q['sql'] or 'FROM "base_user"' in q['sql']
        ]

    assert len(lookups(four_answers)) == len(lookups(one_answer))
