import pytest
from eventyay.base.models import TalkQuestion, TalkQuestionRequired

@pytest.mark.django_db
def test_talk_question_required_after_deadline_no_deadline(event):
    question = TalkQuestion.objects.create(
        event=event,
        question={'en': 'Test Question'},
        question_required=TalkQuestionRequired.AFTER_DEADLINE,
        deadline=None,
    )
    # This should not raise a TypeError
    assert question.required is False
