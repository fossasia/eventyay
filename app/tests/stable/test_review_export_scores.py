from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from django_scopes import scope

from eventyay.base.models import Review, ReviewScore, ReviewScoreCategory, User
from eventyay.base.models.submission import Submission
from eventyay.orga.forms.review import ReviewExportForm


@pytest.fixture
def reviewer(db):
    return User.objects.create_user(
        email='reviewer@example.com',
        password='reviewerpass123',
        fullname='Reviewer',
        locale='en',
    )


@pytest.fixture
def exporter(db):
    return User.objects.create_user(
        email='exporter@example.com',
        password='exporterpass123',
        fullname='Exporter',
        locale='en',
        is_administrator=True,
    )


@pytest.fixture
def categories(event):
    with scope(event=event):
        # The default category, named "Score" like the total score column
        main = event.score_categories.get()
        relevance = ReviewScoreCategory.objects.create(event=event, name='Relevance')
        return main, relevance


def create_review(event, reviewer, categories, title, values):
    with scope(event=event):
        submission = Submission.objects.create(title=title, event=event, submission_type=event.cfp.default_type)
        review = Review.objects.create(submission=submission, user=reviewer, text='Good')
        review.scores.set(
            ReviewScore.objects.create(category=category, value=value)
            for category, value in zip(categories, values)
        )
        review.save()
        return review


def export_rows(event, exporter, fields):
    form = ReviewExportForm(
        event=event,
        user=exporter,
        data={'target': 'all', 'export_format': 'json', **dict.fromkeys(fields, 'on')},
    )
    assert form.is_valid(), form.errors
    selected = [name for name in form.export_field_names if form.cleaned_data.get(name)]
    return form.get_data(form.get_queryset(), selected, [])


@pytest.mark.django_db
def test_review_export_has_total_and_per_category_scores(event, reviewer, exporter, categories):
    create_review(event, reviewer, categories, 'A talk', (1, 2))
    main, relevance = categories
    with scope(event=event), translation.override('en'):
        (row,) = export_rows(event, exporter, ['score', f'score_{main.pk}', f'score_{relevance.pk}'])

    assert row == {
        'Score': Decimal('3.00'),
        'Score in “Score”': Decimal('1.00'),
        'Score in “Relevance”': Decimal('2.00'),
    }


@pytest.mark.django_db
def test_review_export_skips_unselected_category_scores(event, reviewer, exporter, categories):
    create_review(event, reviewer, categories, 'A talk', (1, 2))
    with scope(event=event), translation.override('en'):
        (row,) = export_rows(event, exporter, ['score', 'text'])

    assert row == {'Score': Decimal('3.00'), 'Text': 'Good'}


@pytest.mark.django_db
def test_review_export_reads_category_scores_from_prefetch(event, reviewer, exporter, categories):
    main, relevance = categories
    fields = ['score', f'score_{main.pk}', f'score_{relevance.pk}']
    create_review(event, reviewer, categories, 'A talk', (1, 2))
    with scope(event=event), translation.override('en'):
        # Warm up settings and permission caches so both counts below start equal
        export_rows(event, exporter, fields)
        with CaptureQueriesContext(connection) as one_review:
            export_rows(event, exporter, fields)

    create_review(event, reviewer, categories, 'Another talk', (0, 1))
    with scope(event=event), translation.override('en'):
        with CaptureQueriesContext(connection) as two_reviews:
            rows = export_rows(event, exporter, fields)

    assert len(rows) == 2
    assert len(two_reviews) == len(one_review)
