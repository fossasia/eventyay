from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import OperationalError, connection, connections, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from django_scopes import scope
from kombu.exceptions import OperationalError as BrokerError

from eventyay.base.models import Event, Review, ReviewScore, ReviewScoreCategory, Track, User
from eventyay.base.models.submission import Submission, SubmissionStates
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
    """Create a review with reusable, labelled score choices."""
    with scope(event=event):
        submission = Submission.objects.create(title=title, event=event, submission_type=event.cfp.default_type)
        review = Review.objects.create(submission=submission, user=reviewer, text='Good')
        review.scores.set(
            ReviewScore.objects.get_or_create(category=category, value=value, defaults={'label': str(value)})[0]
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
    """Adding reviews must not add a separate database query for each category score."""
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


@pytest.mark.django_db
@pytest.mark.parametrize('extra_reviews', (20, 501))
def test_review_recalculation_uses_bounded_queries(event, reviewer, categories, mocker, extra_reviews):
    """Batch score reads and writes rather than issuing queries for each review."""
    first = create_review(event, reviewer, categories, 'First talk', (1, 2))
    with scope(event=event):
        save = mocker.spy(Review, 'save')
        with CaptureQueriesContext(connection) as one_review:
            ReviewScoreCategory.recalculate_scores(event)
        submissions = Submission.objects.bulk_create([
            Submission(event=event, code=f'BATCH{index}', title=f'Talk {index}', submission_type=event.cfp.default_type)
            for index in range(extra_reviews)
        ])
        reviews = Review.objects.bulk_create([
            Review(submission=submission, user=reviewer) for submission in submissions
        ])
        score_ids = list(first.scores.values_list('pk', flat=True))
        Review.scores.through.objects.bulk_create([
            Review.scores.through(review_id=review.pk, reviewscore_id=score_id)
            for review in reviews for score_id in score_ids
        ])
        categories[0].weight = 2
        categories[0].save()
        with CaptureQueriesContext(connection) as many_reviews:
            ReviewScoreCategory.recalculate_scores(event)
        assert len(many_reviews) <= len(one_review) + 3
        assert len(many_reviews) <= 10
        assert set(event.reviews.values_list('score', flat=True)) == {Decimal('4')}
        save.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize('case, expected', (
    ('matching', Decimal('-1.2')), ('unmatched', Decimal('1.2')), ('no_track', Decimal('1.2')),
    ('inactive', Decimal('1.2')), ('empty', None), ('zero', Decimal('0')), ('decimal', Decimal('4.2')),
))
def test_review_recalculation_preserves_scoring_rules(event, reviewer, categories, case, expected):
    """Match normal scoring for tracks, inactive categories, empty scores and decimals."""
    review = create_review(event, reviewer, categories, 'A talk', (Decimal('1.2'), Decimal('-2.4')))
    with scope(event=event):
        matching = Track.objects.create(event=event, name='Matching', color='#000000')
        second = Track.objects.create(event=event, name='Second', color='#111111')
        unrelated = Track.objects.create(event=event, name='Unrelated', color='#222222')
        main, relevance = categories
        relevance.limit_tracks.set([matching, second])
        track = None if case == 'no_track' else unrelated if case == 'unmatched' else matching
        Submission.objects.filter(pk=review.submission_id).update(track=track)
        if case in ('inactive', 'empty'):
            relevance.active = False
            relevance.save()
        if case == 'empty':
            main.active = False
            main.save()
        if case in ('zero', 'decimal'):
            main.weight = 0 if case == 'zero' else Decimal('2.5')
            relevance.weight = 0 if case == 'zero' else Decimal('-0.5')
            main.save()
            relevance.save()
        reference = Review.objects.get(pk=review.pk)
        reference.update_score()
        assert reference.score == expected
        ReviewScoreCategory.recalculate_scores(event)
        review.refresh_from_db()
        assert review.score == expected


@pytest.mark.django_db
def test_review_recalculation_preserves_other_events_and_deleted_submissions(event, reviewer, categories):
    """Keep another event's totals and deleted submissions outside recalculation."""
    live = create_review(event, reviewer, categories, 'Live talk', (1, 2))
    deleted = create_review(event, reviewer, categories, 'Deleted talk', (1, 2))
    other = Event.objects.create(
        organizer=event.organizer, name='Other event', slug='other-event',
        date_from=event.date_from, date_to=event.date_to, currency='USD', locale='en',
    )
    with scope(event=other):
        outside = create_review(other, reviewer, [other.score_categories.get()], 'Other talk', (1,))
        Review.objects.filter(pk=outside.pk).update(score=99)
    with scope(event=event):
        Submission.objects.filter(pk=deleted.submission_id).update(state=SubmissionStates.DELETED)
        Review.all_objects.filter(pk=deleted.pk).update(score=99)
        categories[0].weight = 2
        categories[0].save()
        ReviewScoreCategory.recalculate_scores(event)
        live.refresh_from_db()
        assert live.score == 4
        assert Review.all_objects.get(pk=deleted.pk).score == 99
    with scope(event=other):
        outside.refresh_from_db()
        assert outside.score == 99


def review_settings_data(client, event):
    """Build a browser-equivalent POST payload while preserving the rendered field values."""
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
    client, event, reviewer, exporter, categories, mocker, category_count, django_capture_on_commit_callbacks
):
    """Rejecting all independent scores must also preserve the phase and exported total."""
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
        recalculate = mocker.patch('eventyay.submission.tasks.recalculate_all_review_scores.apply_async')
        mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
        with django_capture_on_commit_callbacks(execute=True):
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
def test_invalid_score_form_preserves_review_phase(
    client, event, exporter, mocker, django_capture_on_commit_callbacks
):
    """A score-field error must undo phase changes saved earlier in the request."""
    with scope(event=event):
        phase = event.review_phases.order_by('position').first()
        phase_name = phase.name
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['phase-0-name'] = 'This phase change must be rolled back'
        data['scores-0-name_0'] = ''
        recalculate = mocker.patch('eventyay.submission.tasks.recalculate_all_review_scores.apply_async')
        mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(event.orga_urls.review_settings, data)

        assert response.status_code == 200
        phase.refresh_from_db()
        assert phase.name == phase_name
        recalculate.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize('change, expected_total', (
    ('independent', 2), ('inactive', 2), ('weight', 4), ('rename', 3), ('required', 3),
))
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
def test_valid_score_configuration_updates_totals_without_broker(
    client, event, reviewer, exporter, categories, mocker, django_capture_on_commit_callbacks,
    change, expected_total
):
    """Commit category changes and their review totals even when the broker is down."""
    with scope(event=event):
        review = create_review(event, reviewer, categories, 'A talk', (1, 2))
        client.force_login(exporter)
        data = review_settings_data(client, event)
        if change == 'independent':
            data['scores-0-is_independent'] = 'on'
        elif change == 'inactive':
            data.pop('scores-0-active', None)
        elif change == 'weight':
            data['scores-0-weight'] = '2'
        elif change == 'rename':
            data['scores-0-name_0'] = 'Renamed score'
        else:
            data['scores-0-required'] = 'on'
        recalculate_totals = mocker.spy(ReviewScoreCategory, 'recalculate_scores')
        recalculate = mocker.patch(
            'eventyay.submission.tasks.recalculate_all_review_scores.apply_async',
            side_effect=BrokerError('Broker unavailable'),
        )
        mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(event.orga_urls.review_settings, data)
            assert response.status_code == 302, response.context_data['scores_formset'].errors
            review.refresh_from_db()
            assert review.score == expected_total

        assert response.status_code == 302
        main, relevance = categories
        main.refresh_from_db()
        relevance.refresh_from_db()
        assert main.is_independent is (change == 'independent')
        assert main.active is (change != 'inactive')
        assert main.weight == {'independent': 0, 'weight': 2}.get(change, 1)
        assert not relevance.is_independent and relevance.weight == 1
        if change in ('rename', 'required'):
            recalculate_totals.assert_not_called()
        else:
            recalculate_totals.assert_called_once_with(event)
        recalculate.assert_not_called()


@pytest.mark.django_db
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
def test_review_recalculation_failure_rolls_back_settings(client, event, reviewer, exporter, categories, mocker):
    """Roll back category and phase changes when their score recalculation fails."""
    with scope(event=event):
        review = create_review(event, reviewer, categories, 'A talk', (1, 2))
        phase = event.review_phases.order_by('position').first()
        phase_name = phase.name
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['phase-0-name'] = 'Must be rolled back'
        data.pop('scores-0-active', None)
        original_recalculate = ReviewScoreCategory.recalculate_scores

        def fail_after_recalculation(event):
            """Fail after totals have been written to exercise their rollback."""
            original_recalculate(event)
            raise ValidationError('Cannot recalculate')

        mocker.patch.object(ReviewScoreCategory, 'recalculate_scores', side_effect=fail_after_recalculation)

        response = client.post(event.orga_urls.review_settings, data)

        assert response.status_code == 200
        assert b'Cannot recalculate' in response.content
        categories[0].refresh_from_db()
        phase.refresh_from_db()
        review.refresh_from_db()
        assert categories[0].active
        assert phase.name == phase_name
        assert review.score == 3


@pytest.mark.django_db(transaction=True, available_apps=[app.name for app in apps.get_app_configs()])
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row-lock contention.')
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
def test_concurrent_review_settings_wait_before_validating(client, mocker, request):
    """A competing save must wait for the current event's scoring transaction before validation."""
    mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
    event = request.getfixturevalue('event')
    exporter = request.getfixturevalue('exporter')
    categories = request.getfixturevalue('categories')
    with scope(event=event):
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['scores-1-is_independent'] = 'on'
        mocker.patch('eventyay.submission.tasks.recalculate_all_review_scores.apply_async')
        validate = mocker.spy(ReviewScoreCategory, '_validate_independence')

        def competing_save():
            """Use another database connection to submit a stale scoring form."""
            try:
                competing_client = client.__class__()
                competing_client.force_login(exporter)
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '500ms'")
                try:
                    return competing_client.post(event.orga_urls.review_settings, data).status_code
                except OperationalError as error:
                    return error.__cause__.sqlstate
            finally:
                connections.close_all()

        with transaction.atomic():
            Event.objects.select_for_update().get(pk=event.pk)
            main, relevance = categories
            main.is_independent = True
            main.save()
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = executor.submit(competing_save).result(timeout=30)

            assert result == '55P03'  # PostgreSQL lock timeout.
            assert validate.call_count == 1

        response = client.post(event.orga_urls.review_settings, data)
        assert response.status_code == 302
        assert event.score_categories.filter(is_independent=False).exists()
        main.refresh_from_db()
        relevance.refresh_from_db()
        assert not main.is_independent
        assert relevance.is_independent
