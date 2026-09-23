import csv
from io import BytesIO, StringIO

import pytest

from eventyay.base.services.orderimport import parse_csv


HEADERS = [
    'Session ID',
    'Title',
    'Abstract',
    'Speaker names',
    'Speaker emails',
    'Session type',
    'Room',
]


def build_csv(abstract, delimiter=','):
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, quoting=csv.QUOTE_ALL)
    writer.writerow(HEADERS)
    writer.writerow(
        [
            'ABC12',
            'Intro to Python',
            abstract,
            'Deepak Koul',
            'deepak@example.org',
            'Talk (30 minutes)',
            'Room 1',
        ]
    )
    return BytesIO(buffer.getvalue().encode())


def parse_single_row(abstract, delimiter=','):
    parsed = parse_csv(build_csv(abstract, delimiter=delimiter))
    rows = list(parsed)
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize(
    'abstract',
    (
        'A plain abstract',
        'An abstract with a "quoted" word',
        'He said "hello", then we built an app',
        'First line\nSecond line with a "quote"',
        'Ends with a quote "',
    ),
)
def test_columns_stay_aligned(abstract):
    row = parse_single_row(abstract)

    assert row['Abstract'] == abstract
    assert row['Speaker names'] == 'Deepak Koul'
    assert row['Speaker emails'] == 'deepak@example.org'
    assert row['Session type'] == 'Talk (30 minutes)'
    assert row['Room'] == 'Room 1'


def test_semicolon_separated_file():
    row = parse_single_row('He said "hello"; then we built an app', delimiter=';')

    assert row['Abstract'] == 'He said "hello"; then we built an app'
    assert row['Speaker names'] == 'Deepak Koul'


def test_all_rows_are_returned():
    buffer = StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow(HEADERS)
    for index in range(21):
        writer.writerow(
            [
                f'CODE{index}',
                f'Session {index}',
                f'An abstract with a "quote" and a, comma ({index})',
                f'Speaker {index}',
                f'speaker{index}@example.org',
                'Talk (30 minutes)',
                'Room 1',
            ]
        )

    rows = list(parse_csv(BytesIO(buffer.getvalue().encode())))

    assert len(rows) == 21
    assert [row['Speaker names'] for row in rows] == [f'Speaker {index}' for index in range(21)]
