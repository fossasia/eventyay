import csv
import io

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django_scopes import scopes_disabled

from eventyay.base.models import LogEntry, ProductCategory


def logs_url(event, query=''):
    return f'/control/event/{event.organizer.slug}/{event.slug}/logs/{query}'


def export_rows(response):
    assert response.status_code == 200
    assert response['Content-Type'] == 'text/csv'
    content = b''.join(response.streaming_content).decode()
    return list(csv.reader(io.StringIO(content)))


@pytest.fixture
def logs(event, user):
    """30 team actions, more than fit on one page of the log, and one customer action."""
    with scopes_disabled():
        for _ in range(30):
            event.log_action('eventyay.event.changed', user=user)
        event.log_action('eventyay.event.changed')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_export_contains_every_log_entry(organizer_client, event, logs):
    response = organizer_client.get(logs_url(event, '?download=yes'))

    rows = export_rows(response)
    assert response['Content-Disposition'] == f'attachment; filename="{event.slug}-logs.csv"'
    assert rows[0] == ['Date', 'User', 'Object', 'Action']
    assert len(rows) == 1 + 31
    assert [row[1] for row in rows[1:]].count('Test User') == 30


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_export_keeps_the_current_filter(organizer_client, event, logs):
    team_rows = export_rows(organizer_client.get(logs_url(event, '?user=yes&download=yes')))[1:]
    customer_rows = export_rows(organizer_client.get(logs_url(event, '?user=no&download=yes')))[1:]

    assert len(team_rows) == 30
    assert {row[1] for row in team_rows} == {'Test User'}
    assert len(customer_rows) == 1
    assert customer_rows[0][1] == ''


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    'name',
    ['=HYPERLINK("https://example.org")', ' =1+1', '\n=1+1', '@SUM(A1:A2)', '-2+3'],
)
def test_export_does_not_turn_text_into_formulas(organizer_client, event, user, name):
    with scopes_disabled():
        user.fullname = name
        user.save()
        event.log_action('eventyay.event.changed', user=user)

    rows = export_rows(organizer_client.get(logs_url(event, '?download=yes')))

    assert rows[1][1] == f"'{name}"


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_export_keeps_only_the_text_of_html_actions(organizer_client, event, user, monkeypatch):
    with scopes_disabled():
        event.log_action('eventyay.event.changed', user=user)
    monkeypatch.setattr(LogEntry, 'display', lambda self: 'Moved to <a href="/x">Room &amp; Hall</a>')

    rows = export_rows(organizer_client.get(logs_url(event, '?download=yes')))

    assert rows[1][3] == 'Moved to Room & Hall'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_export_loads_the_logged_objects_together(organizer_client, event, user):
    """The logged objects are loaded together, not with one query per log entry."""

    def log_categories(count):
        with scopes_disabled():
            for i in range(count):
                category = ProductCategory.objects.create(event=event, name=f'Category {i}')
                category.log_action('eventyay.event.category.added', user=user)

    def export_category_queries():
        with CaptureQueriesContext(connection) as queries:
            rows = export_rows(organizer_client.get(logs_url(event, '?download=yes')))
        category_queries = [q for q in queries if f'FROM "{ProductCategory._meta.db_table}"' in q['sql']]
        return len(rows), len(category_queries)

    log_categories(2)
    few_rows, few_queries = export_category_queries()
    log_categories(10)
    many_rows, many_queries = export_category_queries()

    assert (few_rows, many_rows) == (1 + 2, 1 + 12)
    assert many_queries == few_queries == 1


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_logs_page_links_the_export_with_the_current_filter(organizer_client, event, logs):
    response = organizer_client.get(logs_url(event, '?user=yes'))

    assert response.status_code == 200
    assert 'href="?user=yes&amp;download=yes"' in response.content.decode()
