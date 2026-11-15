from datetime import UTC, datetime

import pytest

from eventyay.base.models import Event, Organizer


# The fallback shows the current month or week, so the view's clock is fixed in every test.
TODAY = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
CURRENT_MONTH = '2026-03-01'
CURRENT_WEEK = [2026, 11]

OUT_OF_RANGE_MONTHS = [
    'year=0&month=5',
    'year=1&month=1',
    'year=9999&month=12',
    'year=10000&month=1',
    'year=-5&month=1',
    'year=2026&month=13',
    'year=2026&month=0',
]

OUT_OF_RANGE_WEEKS = [
    'year=0&week=5',
    'year=9999&week=52',
    'year=10000&week=1',
    'year=2026&week=99',
    'year=2026&week=-300',
]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr('eventyay.presale.views.organizer.now', lambda: TODAY)
    organizer = Organizer.objects.create(name='MRMCD e.V.', slug='mrmcd')
    event = Event.objects.create(
        organizer=organizer,
        name='MRMCD series',
        slug='series',
        date_from=datetime(2026, 3, 25, tzinfo=UTC),
        live=True,
        is_public=True,
        has_subevents=True,
    )
    return organizer, event


@pytest.mark.django_db
@pytest.mark.parametrize('query', OUT_OF_RANGE_MONTHS)
@pytest.mark.parametrize('base', ['/mrmcd/', '/mrmcd/widget/product_list', '/mrmcd/series/'])
def test_calendar_falls_back_to_current_month(env, client, base, query):
    r = client.get(f'{base}?style=calendar&{query}')
    assert r.status_code == 200
    if 'widget' in base:
        assert r.json()['date'] == CURRENT_MONTH


@pytest.mark.django_db
@pytest.mark.parametrize('query', OUT_OF_RANGE_WEEKS)
@pytest.mark.parametrize('base', ['/mrmcd/', '/mrmcd/widget/product_list', '/mrmcd/series/'])
def test_week_calendar_falls_back_to_current_week(env, client, base, query):
    r = client.get(f'{base}?style=week&{query}')
    assert r.status_code == 200
    if 'widget' in base:
        assert r.json()['week'] == CURRENT_WEEK
