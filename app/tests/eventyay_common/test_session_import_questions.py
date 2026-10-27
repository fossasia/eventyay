from contextlib import contextmanager

import pytest
from django.core.files.base import ContentFile
from django.db import transaction
from django_scopes import scope

from eventyay.base.models import Answer, AnswerOption, CachedFile, Submission
from eventyay.base.models import TalkQuestion as Question
from eventyay.base.models import TalkQuestionVariant as QuestionVariant
from eventyay.base.models.question import TalkQuestionRequired as QuestionRequired
from eventyay.base.models.question import TalkQuestionTarget
from eventyay.base.models.submission import SubmissionStates
from eventyay.base.models.type import SubmissionType
from eventyay.base.services.talkimport import (
    ImportExecutionError,
    _apply_new_question_mappings,
    _get_or_create_csv_question,
    _import_submission_row,
    _load_mapped_questions,
    import_submissions,
)
from eventyay.common.session_video import (
    SESSION_VIDEO_IMPORT_KEY,
    ensure_session_video_question,
    get_session_video_question,
    get_submission_video_urls,
    parse_imported_video_urls,
    set_submission_video_urls,
)
from eventyay.orga.forms.importers import SessionImportProcessForm
from eventyay.orga.forms.schedule import ScheduleExportForm


def _create_question(event, *, question, variant, target, required=QuestionRequired.OPTIONAL, active=True):
    return Question.objects.create(
        event=event,
        question=question,
        variant=variant,
        target=target,
        question_required=required,
        active=active,
    )


def _choice_cache(question):
    return {
        question.pk: (
            question,
            {str(option.answer).strip().casefold(): option for option in question.options.all()},
        )
    }


def _session_caches(event, **overrides):
    sub_type = SubmissionType.objects.create(event=event, name='Talk')
    caches = {
        'submission_types': [sub_type],
        'tracks': [],
        'rooms': [],
        'valid_states': {choice[0] for choice in SubmissionStates.get_choices()},
        'default_sub_type': sub_type,
        'question_mappings': [],
        'question_cache': {},
        'import_questions': {},
        'import_question_positions': {},
    }
    caches.update(overrides)
    return caches


@pytest.mark.django_db
def test_session_import_form_allows_unmapped_required_question(event):
    with scope(event=event):
        question = _create_question(
            event,
            question='Session level',
            variant=QuestionVariant.STRING,
            target=TalkQuestionTarget.SUBMISSION,
            required=QuestionRequired.REQUIRED,
        )
        form = SessionImportProcessForm(
            data={
                'title': 'csv:Title',
                f'question_{question.pk}': '',
            },
            headers=['Title'],
            event=event,
        )

        assert form.fields[f'question_{question.pk}'].required is False
        assert form.is_valid(), form.errors
        assert form.cleaned_data[f'question_{question.pk}'] == ''


@pytest.mark.django_db
def test_session_import_form_offers_create_for_unmapped_column(event):
    with scope(event=event):
        form = SessionImportProcessForm(
            headers=['Proposal title', 'Audience takeaway'],
            event=event,
        )

        assert form.fields['title'].initial == 'csv:Proposal title'
        assert 'create_question_enabled_audience-takeaway' in form.fields
        assert form.fields['create_question_enabled_audience-takeaway'].initial is True
        assert len(form.new_question_rows) == 1
        assert form.new_question_rows[0]['header'] == 'Audience takeaway'


@pytest.mark.django_db
def test_session_import_form_maps_export_columns(event):
    with scope(event=event):
        form = SessionImportProcessForm(
            headers=['Proposal title', 'Proposal state', 'Speaker IDs', 'Speaker names', 'Duration'],
            event=event,
        )

        assert form.fields['title'].initial == 'csv:Proposal title'
        assert form.fields['state'].initial == 'csv:Proposal state'
        assert form.fields['linked_speakers'].initial == 'csv:Speaker IDs'
        assert form.fields['speakers'].initial == 'csv:Speaker names'
        assert form.fields['duration'].initial == 'csv:Duration'
        assert form.new_question_rows == []


@pytest.mark.django_db
def test_session_import_form_maps_session_video_headers(event):
    with scope(event=event):
        form = SessionImportProcessForm(
            headers=['Proposal title', 'Session videos', 'Video'],
            event=event,
        )

        assert form.fields['session_videos'].initial == 'csv:Session videos'
        assert all(row['header'] not in {'Session videos', 'Video'} for row in form.new_question_rows)


@pytest.mark.django_db
def test_session_import_form_maps_matching_dest_question_by_name(event):
    with scope(event=event):
        question = _create_question(
            event,
            question='Audience takeaway',
            variant=QuestionVariant.STRING,
            target=TalkQuestionTarget.SUBMISSION,
        )
        form = SessionImportProcessForm(
            headers=['Proposal title', 'Audience takeaway'],
            event=event,
            initial={f'question_{question.pk}': 'csv:Old source header'},
        )

        assert form.fields[f'question_{question.pk}'].initial == 'csv:Audience takeaway'
        assert all(row['header'] != 'Audience takeaway' for row in form.new_question_rows)


@pytest.mark.django_db
def test_session_import_form_skips_reserved_export_headers(event):
    with scope(event=event):
        form = SessionImportProcessForm(
            headers=[
                'Proposal title',
                'ID',
                'Speaker IDs',
                'Speaker names',
                'Pending proposal state',
                'Created',
                'Slot Count',
                'Session image',
                'Median score',
                'Average (mean) score',
                'Resources',
                'Start (date)',
                'Start (time)',
                'End (date)',
                'End (time)',
                'Session videos',
                'Video',
            ],
            event=event,
        )

        assert form.new_question_rows == []


@pytest.mark.django_db
def test_session_import_form_does_not_auto_create_when_dest_has_questions(event):
    with scope(event=event):
        _create_question(
            event,
            question='Audience takeaway',
            variant=QuestionVariant.STRING,
            target=TalkQuestionTarget.SUBMISSION,
        )
        form = SessionImportProcessForm(
            headers=['Proposal title', 'T-shirt size'],
            event=event,
        )

        assert form.fields['create_question_enabled_t-shirt-size'].initial is False


@pytest.mark.django_db
def test_import_submission_row_saves_mapped_question_answer(event, user):
    with scope(event=event):
        question = _create_question(
            event,
            question='Audience takeaway',
            variant=QuestionVariant.STRING,
            target=TalkQuestionTarget.SUBMISSION,
        )
        caches = _session_caches(
            event,
            question_mappings=[(question.pk, 'csv:takeaway')],
            question_cache={question.pk: (question, None)},
        )

        created = _import_submission_row(
            event,
            {'title': 'csv:title'},
            {'title': 'A mapped talk', 'takeaway': 'Leave with a plan'},
            user,
            caches=caches,
        )

        assert created is True
        answer = Answer.objects.get(question=question, submission__title='A mapped talk')
        assert answer.answer == 'Leave with a plan'


@pytest.mark.django_db
def test_import_submission_row_creates_and_maps_new_question(event, user):
    with scope(event=event):
        settings = {
            'title': 'csv:title',
            'new_questions': [
                {
                    'header': 'takeaway',
                    'label': 'Audience takeaway',
                    'variant': QuestionVariant.STRING,
                    'mapping': 'csv:takeaway',
                }
            ],
        }
        mappings, cache = _load_mapped_questions(event, settings, target=TalkQuestionTarget.SUBMISSION)
        caches = _session_caches(event)
        mappings, cache = _apply_new_question_mappings(
            event,
            settings,
            mappings,
            cache,
            target=TalkQuestionTarget.SUBMISSION,
            caches=caches,
        )
        caches['question_mappings'] = mappings
        caches['question_cache'] = cache

        created = _import_submission_row(
            event,
            settings,
            {'title': 'A created-field talk', 'takeaway': 'Ship the feature'},
            user,
            caches=caches,
        )

        assert created is True
        question = Question.objects.get(event=event, target=TalkQuestionTarget.SUBMISSION)
        assert str(question.question) == 'Audience takeaway'
        answer = Answer.objects.get(question=question, submission__title='A created-field talk')
        assert answer.answer == 'Ship the feature'


@pytest.mark.django_db
def test_import_submission_row_rejects_unknown_choice_and_cleans_up(event, user):
    with scope(event=event):
        question = _create_question(
            event,
            question='Session level',
            variant=QuestionVariant.CHOICES,
            target=TalkQuestionTarget.SUBMISSION,
        )
        AnswerOption.objects.create(question=question, answer='beginner')
        caches = _session_caches(
            event,
            question_mappings=[(question.pk, 'csv:level')],
            question_cache=_choice_cache(question),
        )

        with pytest.raises(ImportExecutionError, match='Invalid answer'):
            _import_submission_row(
                event,
                {'title': 'csv:title'},
                {'title': 'A new talk', 'level': 'unknown'},
                user,
                caches=caches,
            )

        assert not Submission.objects.filter(event=event, title='A new talk').exists()
        assert not Answer.objects.filter(question=question).exists()


@pytest.mark.django_db
def test_import_submission_row_rejects_unknown_choice_on_optionless_question(event, user):
    with scope(event=event):
        question = _create_question(
            event,
            question='Session level',
            variant=QuestionVariant.CHOICES,
            target=TalkQuestionTarget.SUBMISSION,
        )
        caches = _session_caches(
            event,
            question_mappings=[(question.pk, 'csv:level')],
            question_cache=_choice_cache(question),
        )

        with pytest.raises(ImportExecutionError, match='Invalid answer'):
            _import_submission_row(
                event,
                {'title': 'csv:title'},
                {'title': 'A new talk', 'level': 'unknown'},
                user,
                caches=caches,
            )

        assert not AnswerOption.objects.filter(question=question).exists()
        assert not Submission.objects.filter(event=event, title='A new talk').exists()


def test_parse_imported_video_urls_accepts_newlines_and_commas():
    urls = parse_imported_video_urls(
        'https://www.youtube.com/watch?v=BdDK7ikz5tU\n'
        'https://www.youtube.com/watch?v=7q7f_3jljgs, https://www.youtube.com/watch?v=f_1D_2bUAMWU'
    )
    assert urls == [
        'https://www.youtube.com/watch?v=BdDK7ikz5tU',
        'https://www.youtube.com/watch?v=7q7f_3jljgs',
        'https://www.youtube.com/watch?v=f_1D_2bUAMWU',
    ]


@pytest.mark.django_db
def test_import_submission_row_saves_session_videos(event, user):
    with scope(event=event):
        created = _import_submission_row(
            event,
            {'title': 'csv:title', 'session_videos': 'csv:videos'},
            {
                'title': 'A video talk',
                'videos': (
                    'https://www.youtube.com/watch?v=BdDK7ikz5tU\n'
                    'https://www.youtube.com/watch?v=7q7f_3jljgs'
                ),
            },
            user,
            caches=_session_caches(event),
        )

        assert created is True
        submission = Submission.objects.get(event=event, title='A video talk')
        question = get_session_video_question(event, create=False)
        assert question is not None
        assert question.import_key == SESSION_VIDEO_IMPORT_KEY
        assert question.active is True
        assert question.is_public is False
        assert get_submission_video_urls(submission) == [
            'https://www.youtube.com/watch?v=BdDK7ikz5tU',
            'https://www.youtube.com/watch?v=7q7f_3jljgs',
        ]


@pytest.mark.django_db
def test_create_video_question_reuses_canonical_session_video_field(event):
    with scope(event=event):
        question = _get_or_create_csv_question(
            event,
            TalkQuestionTarget.SUBMISSION,
            {
                'label': 'Video',
                'variant': QuestionVariant.VIDEO,
                'header': 'Video',
                'mapping': 'csv:Video',
            },
            {},
        )
        canonical = get_session_video_question(event, create=False)
        assert canonical is not None
        assert question.pk == canonical.pk
        assert question.import_key == SESSION_VIDEO_IMPORT_KEY


@pytest.mark.django_db
def test_session_export_includes_session_videos_column(event):
    with scope(event=event):
        ensure_session_video_question(event)
        sub_type = SubmissionType.objects.create(event=event, name='Talk')
        submission = Submission.objects.create(
            event=event,
            title='Do not Smile Back',
            submission_type=sub_type,
            state=SubmissionStates.SUBMITTED,
        )
        set_submission_video_urls(
            submission,
            [
                'https://www.youtube.com/watch?v=BdDK7ikz5tU',
                'https://www.youtube.com/watch?v=7q7f_3jljgs',
            ],
        )
        form = ScheduleExportForm(
            event=event,
            data={
                'export_format': 'csv',
                'target': ['all'],
                'title': True,
                'session_videos': True,
            },
        )
        assert form.is_valid(), form.errors
        data = form.get_data(form.get_queryset(), ['title', 'session_videos'], [])

        assert data[0]['Session videos'] == (
            'https://www.youtube.com/watch?v=BdDK7ikz5tU\n'
            'https://www.youtube.com/watch?v=7q7f_3jljgs'
        )


@pytest.mark.django_db
def test_session_export_omits_videos_when_session_videos_disabled(event):
    with scope(event=event):
        question = ensure_session_video_question(event)
        sub_type = SubmissionType.objects.create(event=event, name='Talk')
        submission = Submission.objects.create(
            event=event,
            title='Hidden video talk',
            submission_type=sub_type,
            state=SubmissionStates.SUBMITTED,
        )
        set_submission_video_urls(
            submission,
            ['https://www.youtube.com/watch?v=BdDK7ikz5tU'],
        )
        question.active = False
        question.save(update_fields=['active'])

        form = ScheduleExportForm(
            event=event,
            data={
                'export_format': 'csv',
                'target': ['all'],
                'title': True,
                'session_videos': True,
            },
        )
        assert form.is_valid(), form.errors
        data = form.get_data(form.get_queryset(), ['title', 'session_videos'], [])

        assert data[0]['Session videos'] == ''


@pytest.mark.django_db
def test_session_export_checks_session_videos_enabled_once(event, monkeypatch):
    calls = []

    def counting_enabled(export_event):
        calls.append(export_event.pk)
        return True

    monkeypatch.setattr('eventyay.orga.forms.schedule.session_videos_enabled', counting_enabled)
    with scope(event=event):
        ensure_session_video_question(event)
        sub_type = SubmissionType.objects.create(event=event, name='Talk')
        for index in range(3):
            submission = Submission.objects.create(
                event=event,
                title=f'Talk {index}',
                submission_type=sub_type,
                state=SubmissionStates.SUBMITTED,
            )
            set_submission_video_urls(submission, [f'https://www.youtube.com/watch?v=abcdefghij{index}'])

        form = ScheduleExportForm(
            event=event,
            data={
                'export_format': 'csv',
                'target': ['all'],
                'title': True,
                'session_videos': True,
            },
        )
        assert form.is_valid(), form.errors
        data = form.get_data(form.get_queryset(), ['title', 'session_videos'], [])

        assert len(data) == 3
        assert calls == [event.pk]


@pytest.mark.django_db
def test_import_submissions_removes_new_question_when_no_rows_import(event, user):
    cached = CachedFile.objects.create(type='text/csv', filename='sessions.csv')
    cached.file.save('sessions.csv', ContentFile(b'title,takeaway\n,Ship the feature\n'))
    settings = {
        'title': 'csv:title',
        'new_questions': [
            {
                'header': 'takeaway',
                'label': 'Audience takeaway',
                'variant': QuestionVariant.STRING,
                'mapping': 'csv:takeaway',
            }
        ],
    }

    result = import_submissions(
        event=event.pk,
        fileid=str(cached.id),
        settings=settings,
        locale='en',
        user_id=user.pk,
    )

    assert result['created'] == 0
    assert result['skipped'] == 1
    with scope(event=event):
        assert not Question.all_objects.filter(event=event, target=TalkQuestionTarget.SUBMISSION).exists()


@pytest.mark.django_db
def test_import_submission_row_keeps_reactivated_video_field_private(event, user):
    with scope(event=event):
        question = ensure_session_video_question(event)
        question.active = False
        question.is_public = True
        question.save(update_fields=['active', 'is_public'])

        _import_submission_row(
            event,
            {'title': 'csv:title', 'session_videos': 'csv:videos'},
            {'title': 'A video talk', 'videos': 'https://www.youtube.com/watch?v=BdDK7ikz5tU'},
            user,
            caches=_session_caches(event),
        )

        question.refresh_from_db()
        assert question.active is True
        assert question.is_public is False


@pytest.mark.django_db
def test_import_submission_row_rejects_invalid_video_url_and_cleans_up(event, user):
    with scope(event=event):
        with pytest.raises(ImportExecutionError, match='Invalid session video URL "https://example.com/talk"'):
            _import_submission_row(
                event,
                {'title': 'csv:title', 'session_videos': 'csv:videos'},
                {
                    'title': 'A video talk',
                    'videos': 'https://www.youtube.com/watch?v=BdDK7ikz5tU\nhttps://example.com/talk',
                },
                user,
                caches=_session_caches(event),
            )

        assert not Submission.objects.filter(event=event, title='A video talk').exists()
        assert get_session_video_question(event, create=False) is None



def _insert_before_next_savepoint(monkeypatch, insert):
    real_atomic = transaction.atomic
    state = {'pending': True}

    @contextmanager
    def racing_atomic(*args, **kwargs):
        if state['pending']:
            state['pending'] = False
            insert()
        with real_atomic(*args, **kwargs):
            yield

    monkeypatch.setattr(transaction, 'atomic', racing_atomic)


@pytest.mark.django_db
def test_get_or_create_csv_question_reuses_question_created_concurrently(event, monkeypatch):
    from eventyay.base.services import talkimport

    spec = {
        'header': 'takeaway',
        'label': 'Audience takeaway',
        'variant': QuestionVariant.STRING,
        'mapping': 'csv:takeaway',
    }
    import_key = talkimport._build_import_question_key(
        TalkQuestionTarget.SUBMISSION, talkimport._normalize_extra_key(spec['label'])
    )
    _insert_before_next_savepoint(
        monkeypatch,
        lambda: Question.objects.create(
            event=event,
            target=TalkQuestionTarget.SUBMISSION,
            import_key=import_key,
            variant=QuestionVariant.STRING,
            question='Audience takeaway',
        ),
    )
    with scope(event=event):
        caches = {}
        question = _get_or_create_csv_question(event, TalkQuestionTarget.SUBMISSION, spec, caches)

        assert list(Question.all_objects.filter(event=event, target=TalkQuestionTarget.SUBMISSION)) == [question]
        assert 'question_setup' not in caches


@pytest.mark.django_db
def test_session_video_question_reuses_field_created_concurrently(event, monkeypatch):
    from eventyay.common import session_video

    _insert_before_next_savepoint(monkeypatch, lambda: session_video._create_session_video_question(event))
    with scope(event=event):
        question = ensure_session_video_question(event)

        assert list(Question.all_objects.filter(event=event, import_key=SESSION_VIDEO_IMPORT_KEY)) == [question]
