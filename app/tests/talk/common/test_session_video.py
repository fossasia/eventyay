import pytest
from django import forms
from django_scopes import scope

from eventyay.base.models import Answer, TalkQuestion, TalkQuestionTarget, TalkQuestionVariant
from eventyay.common.session_video import (
    SESSION_VIDEO_IMPORT_KEY,
    ensure_session_video_question,
    get_session_video_question,
    get_submission_video_url,
    get_submission_video_urls,
    set_submission_video_url,
    set_submission_video_urls,
)
from eventyay.common.video_embed import parse_video_urls
from eventyay.orga.forms.cfp import CfPSettingsForm, TalkQuestionForm
from eventyay.submission.forms import TalkQuestionsForm


def cfp_settings_form_data(event, **overrides):
    form = CfPSettingsForm(obj=event, read_only=False)
    data = {}
    for name, field in form.fields.items():
        initial = form.initial.get(name, field.initial)
        if isinstance(field, forms.BooleanField):
            data[name] = bool(initial)
        else:
            data[name] = initial if initial is not None else ''
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_get_session_video_question_creates_canonical_field(event):
    with scope(event=event):
        assert get_session_video_question(event, create=False) is None
        question = get_session_video_question(event, create=True)
        assert question is not None
        assert question.variant == TalkQuestionVariant.VIDEO
        assert question.target == TalkQuestionTarget.SUBMISSION
        assert question.import_key == SESSION_VIDEO_IMPORT_KEY
        assert question.is_public is False
        assert question.active is True
        assert get_session_video_question(event, create=True).pk == question.pk
        assert TalkQuestion.all_objects.filter(
            event=event,
            target=TalkQuestionTarget.SUBMISSION,
            variant=TalkQuestionVariant.VIDEO,
        ).count() == 1


@pytest.mark.django_db
def test_get_session_video_question_adopts_existing_video_field(event):
    with scope(event=event):
        existing = TalkQuestion.objects.create(
            event=event,
            question='Recording',
            variant=TalkQuestionVariant.VIDEO,
            target=TalkQuestionTarget.SUBMISSION,
            is_public=False,
        )
        question = get_session_video_question(event, create=True)
        assert question.pk == existing.pk
        question.refresh_from_db()
        assert question.import_key == SESSION_VIDEO_IMPORT_KEY
        assert question.is_public is False


@pytest.mark.django_db
def test_ensure_session_video_question_deactivates_extra_fields(event):
    with scope(event=event):
        first = TalkQuestion.objects.create(
            event=event,
            question='Video A',
            variant=TalkQuestionVariant.VIDEO,
            target=TalkQuestionTarget.SUBMISSION,
            active=True,
        )
        second = TalkQuestion.objects.create(
            event=event,
            question='Video B',
            variant=TalkQuestionVariant.VIDEO,
            target=TalkQuestionTarget.SUBMISSION,
            active=True,
        )
        question = ensure_session_video_question(event)
        assert question.pk == first.pk
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.active is True
        assert first.import_key == SESSION_VIDEO_IMPORT_KEY
        assert second.active is False


@pytest.mark.django_db
def test_set_submission_video_url_creates_updates_and_clears(event, submission):
    url = 'https://youtu.be/dQw4w9WgXcQ?t=90'
    with scope(event=event):
        assert get_submission_video_url(submission) == ''
        stored = set_submission_video_url(submission, url)
        assert stored == url
        question = get_session_video_question(event, create=False)
        assert question is not None
        assert question.is_public is False
        assert get_submission_video_url(submission) == url
        assert Answer.objects.filter(question=question, submission=submission).count() == 1

        updated = 'https://vimeo.com/123456789#t=1m30s'
        assert set_submission_video_url(submission, updated) == updated
        assert get_submission_video_url(submission) == updated
        assert Answer.objects.filter(question=question, submission=submission).count() == 1

        assert set_submission_video_url(submission, '') == ''
        assert get_submission_video_url(submission) == ''
        assert not Answer.objects.filter(question=question, submission=submission).exists()


@pytest.mark.django_db
def test_set_submission_video_urls_stores_multiple(event, submission):
    urls = [
        'https://youtu.be/dQw4w9WgXcQ?t=90',
        'https://vimeo.com/123456789#t=1m30s',
    ]
    with scope(event=event):
        stored = set_submission_video_urls(submission, urls)
        assert stored == urls
        assert get_submission_video_urls(submission) == urls
        assert get_submission_video_url(submission) == '\n'.join(urls)
        question = get_session_video_question(event, create=False)
        assert Answer.objects.filter(question=question, submission=submission).count() == 1

        assert set_submission_video_urls(submission, []) == []
        assert get_submission_video_urls(submission) == []


@pytest.mark.django_db
def test_set_submission_video_url_rejects_invalid(event, submission):
    with scope(event=event):
        with pytest.raises(ValueError):
            set_submission_video_url(submission, 'https://example.com/watch')
        assert get_session_video_question(event, create=False) is None
        assert get_submission_video_url(submission) == ''


def test_parse_video_urls_splits_lines_and_dedupes():
    assert parse_video_urls('') == []
    assert parse_video_urls('https://youtu.be/aaa\nhttps://vimeo.com/1') == [
        'https://youtu.be/aaa',
        'https://vimeo.com/1',
    ]
    assert parse_video_urls('https://youtu.be/aaa\n\nhttps://youtu.be/aaa') == [
        'https://youtu.be/aaa',
    ]


@pytest.mark.django_db
def test_talk_question_form_hides_video_variant_on_create(event):
    with scope(event=event):
        form = TalkQuestionForm(event=event, initial={'target': TalkQuestionTarget.SUBMISSION})
        assert TalkQuestionVariant.VIDEO not in dict(form.fields['variant'].choices)


@pytest.mark.django_db
def test_session_video_hidden_from_cfp_questions_form(event):
    with scope(event=event):
        question = ensure_session_video_question(event)
        form = CfPSettingsForm(obj=event, read_only=False)
        assert f'question_{question.pk}' not in form.fields


@pytest.mark.django_db
def test_session_video_hidden_from_questions_forms(event, submission):
    with scope(event=event):
        question = ensure_session_video_question(event)
        speaker_form = TalkQuestionsForm(
            event=event,
            submission=submission,
            target=TalkQuestionTarget.SUBMISSION,
            include_session_video=False,
        )
        orga_form = TalkQuestionsForm(
            event=event,
            submission=submission,
            target=TalkQuestionTarget.SUBMISSION,
            include_session_video=False,
        )
        assert f'question_{question.pk}' not in speaker_form.fields
        assert f'question_{question.pk}' not in orga_form.fields


@pytest.mark.django_db
def test_session_video_builtin_on_cfp_settings_form(event):
    with scope(event=event):
        question = ensure_session_video_question(event)
        form = CfPSettingsForm(obj=event, read_only=False)
        assert 'cfp_ask_session_videos' in form.fields
        assert 'cfp_public_session_videos' not in form.fields
        assert f'question_{question.pk}' not in form.fields


@pytest.mark.django_db
def test_session_video_hidden_from_cfp_info_form(event, submission):
    with scope(event=event):
        question = ensure_session_video_question(event)
        from eventyay.submission.forms import InfoForm

        form = InfoForm(event=event, instance=submission)
        assert f'question_{question.pk}' not in form.fields


@pytest.mark.django_db
def test_cfp_settings_form_syncs_session_videos_question(event):
    with scope(event=event):
        form_data = cfp_settings_form_data(
            event,
            cfp_ask_session_videos='optional',
        )
        form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        assert form.is_valid(), form.errors
        form.save()
        question = get_session_video_question(event, create=False)
        assert question is not None
        assert question.active is True
        assert question.is_public is True

        form_data = cfp_settings_form_data(
            event,
            cfp_ask_session_videos='do_not_ask',
        )
        form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        assert form.is_valid(), form.errors
        form.save()
        question.refresh_from_db()
        assert question.active is False
        assert question.is_public is False


@pytest.mark.django_db
def test_session_videos_disabled_hides_urls_but_preserves_data(event, submission):
    with scope(event=event):
        question = ensure_session_video_question(event)
        url = 'https://youtu.be/dQw4w9WgXcQ?t=90'
        set_submission_video_urls(submission, [url])
        question.active = False
        question.is_public = False
        question.save(update_fields=['active', 'is_public'])
        assert get_submission_video_urls(submission) == []
        assert get_submission_video_url(submission) == ''
        answer = Answer.objects.get(question=question, submission=submission)
        assert answer.answer == url
        assert set_submission_video_urls(submission, []) == [url]
        question.active = True
        question.is_public = True
        question.save(update_fields=['active', 'is_public'])
        assert get_submission_video_urls(submission) == [url]
