from unittest.mock import MagicMock, patch

import pytest
from django.db import transaction
from django.db.models import ProtectedError
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Submission,
    SubmissionStates,
    SubmissionType,
    TalkQuestion,
    TalkQuestionTarget,
    TalkQuestionVariant,
)


def _hidden_talk_rows(event):
    TalkQuestion.all_objects.create(
        event=event,
        question='Preview clip',
        variant=TalkQuestionVariant.URL,
        target=TalkQuestionTarget.SUBMISSION,
        active=False,
    )
    TalkQuestion.all_objects.create(
        event=event,
        question='Reviewer notes',
        variant=TalkQuestionVariant.TEXT,
        target=TalkQuestionTarget.REVIEWER,
        active=True,
    )
    submission_type = SubmissionType.objects.create(event=event, name='Talk')
    Submission.all_objects.create(
        event=event,
        title='Draft leftover',
        state=SubmissionStates.DRAFT,
        submission_type=submission_type,
    )


@pytest.mark.django_db
def test_default_managers_leave_hidden_rows_that_protect_event_delete(event):
    with scopes_disabled():
        _hidden_talk_rows(event)
        event.talkquestions.all().delete()
        event.submissions.all().delete()
        assert TalkQuestion.all_objects.filter(event=event).exists()
        assert Submission.all_objects.filter(event=event).exists()
        with transaction.atomic():
            with pytest.raises(ProtectedError):
                event.delete()


@pytest.mark.django_db
def test_delete_sub_objects_removes_hidden_talk_rows(event):
    with scopes_disabled():
        _hidden_talk_rows(event)
        empty = MagicMock()
        empty.iterator.return_value = iter([])
        with patch('eventyay.base.models.storage_model.StoredFile') as stored:
            stored.objects.filter.return_value = empty
            event.delete_sub_objects()

        assert not TalkQuestion.all_objects.filter(event=event).exists()
        assert not Submission.all_objects.filter(event=event).exists()
