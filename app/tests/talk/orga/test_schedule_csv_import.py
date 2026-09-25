import csv
from io import BytesIO, StringIO

import pytest
from django.core.files.base import ContentFile
from django_scopes import scope, scopes_disabled

from eventyay.base.models import CachedFile, Event, Room, SpeakerProfile, Submission, User
from eventyay.base.services.orderimport import parse_csv
from eventyay.base.services.talkimport import import_submission_records, import_submissions
from eventyay.orga.forms.schedule import ScheduleExportForm


HEADERS = ['ID', 'Title', 'Abstract', 'Duration', 'Speaker names', 'Session type', 'Room']
DEEPAK_ABSTRACT = 'He said "hello", then we built an app'
ALOSH_ABSTRACT = 'Another talk with "escaped, quotes" and more text'


def export_style_csv(rows, delimiter=',', headers=None):
    """Build CSV the same way schedule export does: unquoted headers, QUOTE_MINIMAL."""
    fieldnames = headers or HEADERS
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def parse_rows(content: str):
    parsed = parse_csv(BytesIO(content.encode('utf-8')))
    assert parsed is not None
    return list(parsed)


def session_row(*, title, abstract, duration, speaker, session_type='Talk (30 minutes)', room='Main Hall', code='ABC12'):
    return {
        'ID': code,
        'Title': title,
        'Abstract': abstract,
        'Duration': duration,
        'Speaker names': speaker,
        'Session type': session_type,
        'Room': room,
    }


def test_parse_csv_accepts_single_column_files():
    rows = parse_rows('ID\nABC12\nXYZ99\n')
    assert [row['ID'] for row in rows] == ['ABC12', 'XYZ99']


def test_parse_csv_keeps_escaped_quotes_with_unquoted_headers():
    content = export_style_csv(
        [
            session_row(
                title="Deepak's Session",
                abstract=DEEPAK_ABSTRACT,
                duration=1,
                speaker='Deepak Koul',
                code='DPK01',
            ),
            session_row(
                title="Alosh's Session",
                abstract=ALOSH_ABSTRACT,
                duration=15,
                speaker='Alosh Denny',
                session_type='Workshop',
                room='Room B',
                code='ALS15',
            ),
        ]
    )

    rows = parse_rows(content)
    assert len(rows) == 2

    deepak, alosh = rows
    assert deepak['Abstract'] == DEEPAK_ABSTRACT
    assert deepak['Duration'] == '1'
    assert deepak['Speaker names'] == 'Deepak Koul'
    assert deepak['Session type'] == 'Talk (30 minutes)'
    assert deepak['Room'] == 'Main Hall'

    assert alosh['Abstract'] == ALOSH_ABSTRACT
    assert alosh['Duration'] == '15'
    assert alosh['Speaker names'] == 'Alosh Denny'
    assert alosh['Session type'] == 'Workshop'
    assert alosh['Room'] == 'Room B'


def test_parse_csv_keeps_multiline_quoted_abstract():
    abstract = 'Line one with "quotes", and a comma.\nLine two still belongs here.'
    content = export_style_csv(
        [session_row(title='Multiline talk', abstract=abstract, duration=30, speaker='Nami')]
    )

    rows = parse_rows(content)
    assert len(rows) == 1
    assert rows[0]['Abstract'] == abstract
    assert rows[0]['Speaker names'] == 'Nami'
    assert rows[0]['Duration'] == '30'


def test_parse_csv_keeps_semicolon_delimited_quoted_fields():
    content = export_style_csv(
        [
            session_row(
                title="Deepak's Session",
                abstract=DEEPAK_ABSTRACT,
                duration=1,
                speaker='Deepak Koul',
            )
        ],
        delimiter=';',
    )

    rows = parse_rows(content)
    assert len(rows) == 1
    assert rows[0]['Abstract'] == DEEPAK_ABSTRACT
    assert rows[0]['Speaker names'] == 'Deepak Koul'
    assert rows[0]['Duration'] == '1'


def test_parse_csv_returns_every_row_of_a_21_session_file():
    rows_in = [
        session_row(
            title=f'Session {index}',
            abstract=f'Abstract {index} mentions "quotes", then continues.',
            duration=1 if index == 1 else 15 if index == 15 else 30,
            speaker='Deepak Koul' if index == 1 else 'Alosh Denny' if index == 15 else f'Speaker {index}',
            code=f'S{index:02d}',
        )
        for index in range(1, 22)
    ]
    content = export_style_csv(rows_in)

    rows = parse_rows(content)
    assert len(rows) == 21
    assert rows[0]['Speaker names'] == 'Deepak Koul'
    assert rows[0]['Duration'] == '1'
    assert rows[14]['Speaker names'] == 'Alosh Denny'
    assert rows[14]['Duration'] == '15'
    assert all(row['Room'] == 'Main Hall' for row in rows)


@pytest.mark.django_db
def test_schedule_export_roundtrip_keeps_quoted_abstract_columns(event, speaker):
    with scope(event=event):
        speaker.fullname = 'Deepak Koul'
        speaker.save(update_fields=['fullname'])
        submission = Submission.objects.create(
            event=event,
            title="Deepak's Session",
            abstract=DEEPAK_ABSTRACT,
            duration=1,
            submission_type=event.cfp.default_type,
            content_locale='en',
        )
        submission.speakers.add(speaker)

        form = ScheduleExportForm(
            event=event,
            data={
                'export_format': 'csv',
                'target': ['all'],
                'title': True,
                'abstract': True,
                'duration': True,
                'speaker_names': True,
                'submission_type': True,
            },
        )
        assert form.is_valid(), form.errors
        response = form.export_data()

    rows = parse_rows(response.content.decode('utf-8'))
    assert len(rows) == 1
    exported = rows[0]
    assert exported['Abstract'] == DEEPAK_ABSTRACT
    assert exported['Speaker names'] == 'Deepak Koul'
    assert str(exported['Duration']) == '1'


@pytest.mark.django_db
def test_schedule_import_does_not_create_numeric_speakers(event, orga_user):
    with scopes_disabled():
        target = Event.objects.create(
            name='Going Merry',
            slug='going-merry',
            email='merry@example.org',
            date_from=event.date_from,
            date_to=event.date_to,
            organizer=event.organiser,
        )

    content = export_style_csv(
        [
            session_row(
                title="Deepak's Session",
                abstract=DEEPAK_ABSTRACT,
                duration=1,
                speaker='Deepak Koul',
                code='DPK01',
            ),
            session_row(
                title="Alosh's Session",
                abstract=ALOSH_ABSTRACT,
                duration=15,
                speaker='Alosh Denny',
                session_type='Workshop',
                room='Room B',
                code='ALS15',
            ),
        ]
    )
    cached = CachedFile.objects.create(type='text/csv', filename='sessions.csv')
    cached.file.save('sessions.csv', ContentFile(content.encode('utf-8')))

    settings = {
        'title': 'csv:Title',
        'abstract': 'csv:Abstract',
        'duration': 'csv:Duration',
        'speakers': 'csv:Speaker names',
        'submission_type': 'csv:Session type',
        'room': 'csv:Room',
    }
    result = import_submissions(
        event=target.pk,
        fileid=str(cached.id),
        settings=settings,
        locale='en',
        user_id=orga_user.pk,
    )

    assert result['created'] == 2
    assert result['skipped'] == 0

    with scope(event=target):
        speaker_names = set(
            SpeakerProfile.objects.filter(event=target).values_list('user__fullname', flat=True)
        )
        assert speaker_names == {'Deepak Koul', 'Alosh Denny'}
        assert '1' not in speaker_names
        assert '15' not in speaker_names

        deepak_talk = Submission.objects.get(event=target, title="Deepak's Session")
        alosh_talk = Submission.objects.get(event=target, title="Alosh's Session")
        assert deepak_talk.abstract == DEEPAK_ABSTRACT
        assert alosh_talk.abstract == ALOSH_ABSTRACT
        assert list(deepak_talk.speakers.values_list('fullname', flat=True)) == ['Deepak Koul']
        assert list(alosh_talk.speakers.values_list('fullname', flat=True)) == ['Alosh Denny']
        room_names = {str(room.name) for room in Room.objects.filter(event=target)}
        assert 'Main Hall' in room_names
        assert 'Room B' in room_names


@pytest.mark.django_db
def test_import_submission_records_keep_quoted_speaker_columns(event, orga_user):
    records = parse_rows(
        export_style_csv(
            [
                session_row(
                    title="Deepak's Session",
                    abstract=DEEPAK_ABSTRACT,
                    duration=1,
                    speaker='Deepak Koul',
                )
            ]
        )
    )
    mapped = [
        {
            'title': row['Title'],
            'abstract': row['Abstract'],
            'duration': row['Duration'],
            'speakers': row['Speaker names'],
            'submission_type': row['Session type'],
            'room': row['Room'],
        }
        for row in records
    ]

    with scope(event=event):
        result = import_submission_records(event, mapped, orga_user)
        assert result['created'] == 1
        assert result['skipped'] == 0
        submission = Submission.objects.get(event=event, title="Deepak's Session")
        assert submission.abstract == DEEPAK_ABSTRACT
        assert list(submission.speakers.values_list('fullname', flat=True)) == ['Deepak Koul']
        assert not User.objects.filter(fullname='1').exists()
