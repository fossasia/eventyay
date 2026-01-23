import pytest
from django_scopes import scope
from eventyay.base.models import TalkQuestion, TalkQuestionRequired

@pytest.mark.django_db
def test_can_add_dependent_question(orga_client, event):
    with scope(event=event):
        assert event.talkquestions.count() == 0

    # Create parent question
    response = orga_client.post(
        event.cfp.urls.new_question,
        {
            "target": "submission",
            "question_0": "Parent Question",
            "variant": "boolean",
            "active": True,
            "question_required": TalkQuestionRequired.REQUIRED,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        event.refresh_from_db()
        assert event.talkquestions.count() == 1
        parent_q = event.talkquestions.first()

    # Create child question dependent on parent (True)
    response = orga_client.post(
        event.cfp.urls.new_question,
        {
            "target": "submission",
            "question_0": "Child Question",
            "variant": "string",
            "active": True,
            "question_required": TalkQuestionRequired.REQUIRED,
            "dependency_question": parent_q.pk,
            "dependency_values": ["True"],
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        event.refresh_from_db()
        assert event.talkquestions.count() == 2
        child_q = event.talkquestions.last()
        assert child_q.dependency_question == parent_q
        assert "True" in child_q.dependency_values

    # Verify form re-render (edit page)
    response = orga_client.get(child_q.urls.edit, follow=True)
    assert response.status_code == 200
    assert str(parent_q.pk) in response.text
