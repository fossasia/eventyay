from sys import exc_info
import pytest
import datetime
from django.core.exceptions import ValidationError
from django_scopes import scope
from eventyay.base.models import TalkQuestion, TalkQuestionVariant, Event, Organizer

@pytest.fixture
def event(db):
    organizer = Organizer.objects.create(
        name="Test Organizer",
        slug="test-org",
    )

    return Event.objects.create(
        organizer=organizer,
        name="Test Event",
        slug="test-event",
        timezone="UTC",
        date_from=datetime.date(2026, 1, 1),
        date_to=datetime.date(2026, 1, 2),
    )

@pytest.mark.django_db
def test_valid_variant_can_be_created(event):
    """Verify that valid variants can be created."""
    with scope(event=event):
        for variant in TalkQuestionVariant.valid_choices:
            question = TalkQuestion.objects.create(
                event=event,
                question=f"Test question for {variant[0]}",
                variant=variant[0],
                target="submission",
            )
            assert question.variant == variant[0]


@pytest.mark.django_db
def test_invalid_variant_is_rejected(event):
    """Verify that invalid variants are rejected at model level."""
    with scope(event=event):
        question = TalkQuestion(
            event=event,
            question="Test question",
            variant="wrong_variant",  
            target="submission",
        )
        with pytest.raises(ValidationError) as exc_info:
            question.full_clean()
        assert "variant" in exc_info.value.message_dict
        messages = exc_info.value.message_dict["variant"]
        assert any("wrong_variant" in message for message in messages)



@pytest.mark.django_db
def test_invalid_variant_update_rejected(event):
    """Verify that updating a question to an invalid variant is rejected."""
    with scope(event=event):
        question = TalkQuestion.objects.create(
            event=event,
            question="Test question",
            variant=TalkQuestionVariant.valid_choices[0][0],
            target="submission",
        )
        question.variant = "wrong_variant"
        with pytest.raises(ValidationError) as exc_info:
            question.full_clean()
        assert "variant" in exc_info.value.message_dict


