import importlib

import pytest
from django.apps import apps
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Answer, Event, TalkQuestion, TalkQuestionTarget, TalkQuestionVariant
from eventyay.person.forms.profile import SpeakerProfileForm


@pytest.mark.django_db
def test_speaker_profile_form_no_duplicate_fields_and_reviewer_visibility(event, speaker):
    """Speaker profile fields come from one form, and reviewers only see visible questions."""
    with scope(event=event):
        visible = TalkQuestion.objects.create(
            event=event,
            question='Visible question',
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SPEAKER,
            is_visible_to_reviewers=True,
        )
        hidden = TalkQuestion.objects.create(
            event=event,
            question='Hidden question',
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SPEAKER,
            is_visible_to_reviewers=False,
        )

        form_orga = SpeakerProfileForm(event=event, user=speaker, for_reviewers=False)
        fields = list(form_orga.fields.keys())
        assert fields.count(f'question_{visible.pk}') == 1
        assert fields.count(f'question_{hidden.pk}') == 1

        form_reviewer = SpeakerProfileForm(event=event, user=speaker, for_reviewers=True)
        fields_reviewer = list(form_reviewer.fields.keys())
        assert f'question_{visible.pk}' in fields_reviewer
        assert f'question_{hidden.pk}' not in fields_reviewer


@pytest.mark.django_db
def test_new_events_do_not_seed_job_title_or_organization(event):
    with scope(event=event):
        assert not TalkQuestion.all_objects.filter(
            event=event,
            import_key__in=['speaker_job_title', 'speaker_organization'],
        ).exists()


@pytest.mark.django_db
def test_event_clone_reuses_matching_import_key(event):
    with scope(event=event):
        TalkQuestion.objects.create(
            event=event,
            question='Shared field',
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SPEAKER,
            import_key='shared_import_key',
            active=False,
        )

    with scopes_disabled():
        dest_event = Event.objects.create(
            name='Dest Event',
            slug='dest',
            organizer=event.organizer,
            date_from=event.date_from,
            date_to=event.date_to,
            timezone=event.timezone,
        )
        with scope(event=dest_event):
            q_dest = TalkQuestion.objects.create(
                event=dest_event,
                question='Destination default',
                variant=TalkQuestionVariant.STRING,
                target=TalkQuestionTarget.SPEAKER,
                import_key='shared_import_key',
                active=True,
            )
        dest_event.copy_data_from(event)

    with scope(event=dest_event):
        q_dest.refresh_from_db()
        assert q_dest.active is False
        assert str(q_dest.question) == 'Shared field'
        assert TalkQuestion.all_objects.filter(event=dest_event, import_key='shared_import_key').count() == 1


@pytest.mark.django_db
def test_revert_migration_removes_seeded_questions_and_their_answers(event, speaker):
    with scope(event=event):
        job_title = TalkQuestion.all_objects.create(
            event=event,
            question='Job Title',
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SPEAKER,
            import_key='speaker_job_title',
            active=False,
        )
        organization = TalkQuestion.objects.create(
            event=event,
            question='Organization',
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SPEAKER,
            import_key='speaker_organization',
        )
        Answer.objects.create(question=organization, person=speaker, answer='Acme')
        custom = TalkQuestion.objects.create(
            event=event,
            question='Custom question',
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SPEAKER,
            import_key='custom_field',
        )
        Answer.objects.create(question=custom, person=speaker, answer='Keep me')

    migration = importlib.import_module('eventyay.base.migrations.0078_revert_default_speaker_questions')
    migration.remove_default_speaker_questions(apps, None)

    with scope(event=event):
        assert not TalkQuestion.all_objects.filter(pk__in=[job_title.pk, organization.pk]).exists()
        assert not Answer.objects.filter(answer='Acme').exists()
        assert TalkQuestion.all_objects.filter(pk=custom.pk).exists()
        assert Answer.objects.get(question=custom).answer == 'Keep me'
