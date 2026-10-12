from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.db import connection
from django.test import override_settings
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


def review_settings_data(client, event):
    response = client.get(event.orga_urls.review_settings)
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    form = page.find('input', attrs={'name': 'scores-TOTAL_FORMS'}).find_parent('form')
    data = {}
    for field in form.select('input[name], select[name], textarea[name]'):
        name = field['name']
        kind = field.get('type')
        if '__prefix__' in name or field.has_attr('disabled') or kind in ('submit', 'button', 'file'):
            continue
        if kind in ('checkbox', 'radio') and not field.has_attr('checked'):
            continue
        if field.name == 'select':
            options = field.select('option[selected]')
            if not options and not field.has_attr('multiple'):
                options = field.select('option')[:1]
            data[name] = [option.get('value', option.text) for option in options]
        elif field.name == 'textarea':
            data[name] = field.text
        else:
            data[name] = field.get('value', 'on' if kind in ('checkbox', 'radio') else '')
    return data


@pytest.mark.django_db
@pytest.mark.parametrize('category_count', (2, 4))
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
def test_rejected_review_scoring_preserves_categories_phases_and_export(
    client, event, reviewer, exporter, categories, mocker, category_count
):
    with scope(event=event):
        all_categories = list(categories)
        for index in range(2, category_count):
            all_categories.append(ReviewScoreCategory.objects.create(event=event, name=f'Category {index + 1}'))
        submission = Submission.objects.create(event=event, title='A talk', submission_type=event.cfp.default_type)
        review = Review.objects.create(submission=submission, user=reviewer, text='Good')
        review_scores = [all_categories[0].scores.get(value=2)]
        review_scores.extend(
            ReviewScore.objects.create(category=category, value=index + 3, label='Good')
            for index, category in enumerate(all_categories[1:])
        )
        review.scores.set(review_scores)
        review.save()
        before = list(event.score_categories.order_by('pk').values_list('is_independent', 'weight'))
        phase = event.review_phases.order_by('position').first()
        phase_name = phase.name
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['phase-0-name'] = 'This phase change must be rolled back'
        for index in range(category_count):
            data[f'scores-{index}-is_independent'] = 'on'
        recalculate = mocker.patch('eventyay.orga.views.event.recalculate_all_review_scores.apply_async')
        response = client.post(event.orga_urls.review_settings, data)

        assert response.status_code == 200
        assert b'You need to keep at least one non-independent score category!' in response.content
        assert list(event.score_categories.order_by('pk').values_list('is_independent', 'weight')) == before
        phase.refresh_from_db()
        assert phase.name == phase_name
        review.refresh_from_db()
        assert review.score == Review.calculate_score(list(review.scores.select_related('category')))
        (row,) = export_rows(event, exporter, ['score'])
        assert row['Score'] == sum(range(2, category_count + 2))
        recalculate.assert_not_called()


@pytest.mark.django_db
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
def test_invalid_score_form_preserves_review_phase(client, event, exporter, mocker):
    with scope(event=event):
        phase = event.review_phases.order_by('position').first()
        phase_name = phase.name
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['phase-0-name'] = 'This phase change must be rolled back'
        data['scores-0-name_0'] = ''
        recalculate = mocker.patch('eventyay.orga.views.event.recalculate_all_review_scores.apply_async')
        response = client.post(event.orga_urls.review_settings, data)

        assert response.status_code == 200
        phase.refresh_from_db()
        assert phase.name == phase_name
        recalculate.assert_not_called()


@pytest.mark.django_db
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
def test_valid_independent_score_configuration_saves(client, event, exporter, categories, mocker):
    with scope(event=event):
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['scores-0-is_independent'] = 'on'
        recalculate = mocker.patch('eventyay.orga.views.event.recalculate_all_review_scores.apply_async')
        response = client.post(event.orga_urls.review_settings, data)

        assert response.status_code == 302
        main, relevance = categories
        main.refresh_from_db()
        relevance.refresh_from_db()
        assert main.is_independent and main.weight == 0
        assert not relevance.is_independent and relevance.weight == 1
        recalculate.assert_called_once_with(kwargs={'event_id': event.pk}, ignore_result=True)
