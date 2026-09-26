import pytest
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, TalkQuestion, TalkQuestionTarget, TalkQuestionVariant
from eventyay.base.models.cfp import default_fields
from eventyay.person.forms.profile import SpeakerProfileForm
from eventyay.person.services import build_public_speaker_role


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
def test_new_events_have_default_speaker_role_fields(event):
    with scope(event=event):
        defaults = default_fields()
        assert event.cfp.fields['job_title'] == defaults['job_title']
        assert event.cfp.fields['organization'] == defaults['organization']


@pytest.mark.django_db
def test_speaker_profile_form_includes_default_role_fields(event, speaker):
    with scope(event=event):
        form = SpeakerProfileForm(event=event, user=speaker)
        assert 'job_title' in form.fields
        assert 'organization' in form.fields


@pytest.mark.django_db
def test_build_public_speaker_role_formats_values(event, speaker):
    with scope(event=event):
        profile = speaker.event_profile(event)
        profile.job_title = 'Founder'
        profile.organization = 'FOSSASIA'
        profile.save(update_fields=['job_title', 'organization'])

        event.cfp.fields['job_title']['public'] = True
        event.cfp.fields['organization']['public'] = True
        event.cfp.save(update_fields=['fields'])

        assert build_public_speaker_role(profile, event) == 'Founder, FOSSASIA'


@pytest.mark.django_db
def test_build_public_speaker_role_single_value_without_separator(event, speaker):
    with scope(event=event):
        profile = speaker.event_profile(event)
        profile.job_title = 'Founder'
        profile.organization = ''
        profile.save(update_fields=['job_title', 'organization'])

        event.cfp.fields['job_title']['public'] = True
        event.cfp.fields['organization']['public'] = True
        event.cfp.save(update_fields=['fields'])

        assert build_public_speaker_role(profile, event) == 'Founder'


@pytest.mark.django_db
def test_build_public_speaker_role_respects_public_toggle(event, speaker):
    with scope(event=event):
        profile = speaker.event_profile(event)
        profile.job_title = 'Founder'
        profile.organization = 'FOSSASIA'
        profile.save(update_fields=['job_title', 'organization'])

        event.cfp.fields['job_title']['public'] = False
        event.cfp.fields['organization']['public'] = True
        event.cfp.save(update_fields=['fields'])

        assert build_public_speaker_role(profile, event) == 'FOSSASIA'


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
        assert q_dest.question == 'Shared field'
        assert TalkQuestion.all_objects.filter(event=dest_event, import_key='shared_import_key').count() == 1

