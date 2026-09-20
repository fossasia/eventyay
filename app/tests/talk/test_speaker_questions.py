import pytest
from django.core.exceptions import ValidationError
from django_scopes import scope, scopes_disabled
from eventyay.base.models import Event, TalkQuestion, TalkQuestionTarget, TalkQuestionVariant, Answer
from eventyay.base.models.cfp import SPEAKER_JOB_TITLE_IMPORT_KEY, SPEAKER_ORGANIZATION_IMPORT_KEY
from eventyay.orga.forms.cfp import TalkQuestionForm
from eventyay.person.forms.profile import SpeakerProfileForm
from eventyay.person.services import build_speaker_role_answers_map

@pytest.mark.django_db
def test_talk_question_form_disables_seeded_fields(event):
    """Test that TalkQuestionForm disables variant and target for default speaker questions."""
    with scope(event=event):
        # Default question is seeded automatically on event creation
        q = TalkQuestion.objects.get(event=event, import_key=SPEAKER_JOB_TITLE_IMPORT_KEY)
        form = TalkQuestionForm(event=event, instance=q)
        assert form.fields['variant'].disabled is True
        assert form.fields['target'].disabled is True

        # Create a non-default question
        q2 = TalkQuestion.objects.create(
            event=event,
            question="Custom Question",
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SPEAKER,
        )
        form2 = TalkQuestionForm(event=event, instance=q2)
        assert form2.fields['variant'].disabled is False
        assert form2.fields['target'].disabled is False

@pytest.mark.django_db
def test_speaker_profile_form_no_duplicate_fields_and_reviewer_visibility(event, speaker):
    """Test that SpeakerProfileForm does not render duplicate questions and respects visibility."""
    with scope(event=event):
        q1 = TalkQuestion.objects.get(event=event, import_key=SPEAKER_JOB_TITLE_IMPORT_KEY)
        q1.is_visible_to_reviewers = True
        q1.save(update_fields=['is_visible_to_reviewers'])
        
        q2 = TalkQuestion.objects.get(event=event, import_key=SPEAKER_ORGANIZATION_IMPORT_KEY)
        q2.is_visible_to_reviewers = False
        q2.save(update_fields=['is_visible_to_reviewers'])
        
        # As an organizer, we should see both, and they shouldn't be duplicated
        form_orga = SpeakerProfileForm(event=event, user=speaker, for_reviewers=False)
        fields = list(form_orga.fields.keys())
        assert f'question_{q1.pk}' in fields
        assert f'question_{q2.pk}' in fields
        # Check no duplicates for Job Title
        assert fields.count(f'question_{q1.pk}') == 1

        # As a reviewer, we should only see q1
        form_reviewer = SpeakerProfileForm(event=event, user=speaker, for_reviewers=True)
        fields_reviewer = list(form_reviewer.fields.keys())
        assert f'question_{q1.pk}' in fields_reviewer
        assert f'question_{q2.pk}' not in fields_reviewer

@pytest.mark.django_db
def test_build_speaker_role_answers_map_with_none(event, speaker):
    """Test that build_speaker_role_answers_map handles None answers without crashing."""
    with scope(event=event):
        q1 = TalkQuestion.objects.get(event=event, import_key=SPEAKER_JOB_TITLE_IMPORT_KEY)
        q2 = TalkQuestion.objects.get(event=event, import_key=SPEAKER_ORGANIZATION_IMPORT_KEY)
        
        # Do not create an answer for q1 so that dictionary .get() returns None
        Answer.objects.create(person=speaker, question=q2, answer="Acme Corp ")
        
        role_map = build_speaker_role_answers_map([speaker.pk], q1, q2, event)
        assert role_map.get(speaker.pk) == "Acme Corp"

@pytest.mark.django_db
def test_default_questions_cannot_be_deleted(event):
    """Test that default speaker questions raise an error on deletion."""
    with scope(event=event):
        q = TalkQuestion.objects.get(event=event, import_key=SPEAKER_JOB_TITLE_IMPORT_KEY)
        
        with pytest.raises(ValidationError):
            q.delete()

@pytest.mark.django_db
def test_event_clone_reuses_inactive_seeded_questions(event):
    """Test that event cloning correctly reuses inactive seeded questions."""
    with scope(event=event):
        # Fetch seeded question on source event and make it inactive
        q_src = TalkQuestion.objects.get(event=event, import_key=SPEAKER_JOB_TITLE_IMPORT_KEY)
        q_src.active = False
        q_src.save(update_fields=['active'])
    
    # Create destination event that already has a seeded question (as happens during Event creation)
    with scopes_disabled():
        dest_event = Event.objects.create(
            name="Dest Event", 
            slug="dest", 
            organizer=event.organizer,
            date_from=event.date_from,
            date_to=event.date_to,
            timezone=event.timezone
        )
        q_dest = TalkQuestion.objects.get(event=dest_event, import_key=SPEAKER_JOB_TITLE_IMPORT_KEY)
        q_dest.active = True
        q_dest.question = "Job Title Default"
        q_dest.save(update_fields=['active', 'question'])
        
        dest_event.copy_data_from(event)
    
    with scope(event=dest_event):
        # It should reuse q_dest, updating its active status to False and question to "Job Title"
        q_dest.refresh_from_db()
        assert q_dest.active is False
        assert q_dest.question == "Job Title"
        # And no duplicate was created
        assert TalkQuestion.all_objects.filter(event=dest_event, import_key=SPEAKER_JOB_TITLE_IMPORT_KEY).count() == 1
