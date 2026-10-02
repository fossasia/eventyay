import pytest
from django.utils import translation
from django_scopes import scope

from eventyay.base.models import Answer, Event, TalkQuestion, TalkQuestionTarget, TalkQuestionVariant, User
from eventyay.base.models.submission import Submission
from eventyay.orga.views.cfp import CfPQuestionRemind


@pytest.fixture
def speaker(db):
    return User.objects.create_user(
        email='speaker@example.com',
        password='speakerpass123',
        fullname='Speaker',
        locale='en',
    )


@pytest.fixture
def submission(event, speaker):
    Event.objects.filter(pk=event.pk).update(timezone='Europe/Berlin')
    event = Event.objects.get(pk=event.pk)
    with scope(event=event):
        submission = Submission.objects.create(
            title='A talk', event=event, submission_type=event.cfp.default_type
        )
        submission.speakers.add(speaker)
        return submission


@pytest.mark.django_db
@pytest.mark.parametrize(
    'variant,value,expected',
    (
        (TalkQuestionVariant.DATE, '2026-10-15', '2026-10-15'),
        # Stored in UTC, shown in the event's timezone
        (TalkQuestionVariant.DATETIME, '2026-10-15 08:30:00+00:00', '2026-10-15 10:30'),
        (TalkQuestionVariant.DATE, 'not a date', 'not a date'),
        (TalkQuestionVariant.DATE, '', ''),
        (TalkQuestionVariant.DATETIME, '', ''),
    ),
)
def test_date_answer_string(submission, variant, value, expected):
    event = submission.event
    with scope(event=event), translation.override('en'):
        question = TalkQuestion.objects.create(question='When?', variant=variant, event=event)
        answer = Answer.objects.create(question=question, submission=submission, answer=value)
        assert answer.answer_string == expected
        assert answer.is_answered is bool(expected)


@pytest.mark.django_db
@pytest.mark.parametrize('variant', (TalkQuestionVariant.DATE, TalkQuestionVariant.DATETIME))
@pytest.mark.parametrize('target', (TalkQuestionTarget.SUBMISSION, TalkQuestionTarget.SPEAKER))
def test_answered_date_question_is_not_reminded(submission, speaker, variant, target):
    event = submission.event
    with scope(event=event):
        question = TalkQuestion.objects.create(question='When?', variant=variant, event=event, target=target)
        Answer.objects.create(
            question=question,
            submission=submission if target == TalkQuestionTarget.SUBMISSION else None,
            person=speaker if target == TalkQuestionTarget.SPEAKER else None,
            answer='2026-10-15 08:30:00+00:00' if variant == TalkQuestionVariant.DATETIME else '2026-10-15',
        )
        missing = CfPQuestionRemind.get_missing_answers(
            questions=[question], person=speaker, submissions=event.submissions.all()
        )
        assert missing == []
