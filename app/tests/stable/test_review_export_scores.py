from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import OperationalError, connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from django_scopes import scope
from kombu.exceptions import OperationalError as BrokerError

from eventyay.base.models import Event, Review, ReviewScore, ReviewScoreCategory, User
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
    """Create a scored review using valid, unique choices in each category."""
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
    client, event, reviewer, exporter, categories, mocker, category_count
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
    """A score-field error must undo phase changes saved earlier in the request."""
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
def test_valid_independent_score_configuration_saves(
    client, event, reviewer, exporter, categories, mocker, django_capture_on_commit_callbacks
):
    """Independent categories are valid when another category still contributes to the total."""
    with scope(event=event):
        review = create_review(event, reviewer, categories, 'A talk', (1, 2))
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['scores-0-is_independent'] = 'on'
        recalculate = mocker.patch('eventyay.orga.views.event.recalculate_all_review_scores.apply_async')
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(event.orga_urls.review_settings, data)
            recalculate.assert_not_called()

        assert response.status_code == 302
        main, relevance = categories
        main.refresh_from_db()
        relevance.refresh_from_db()
        assert main.is_independent and main.weight == 0
        assert not relevance.is_independent and relevance.weight == 1
        review.refresh_from_db()
        assert review.score == Decimal('2.00')
        recalculate.assert_called_once_with(kwargs={'event_id': event.pk}, ignore_result=True)


@pytest.mark.django_db
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
@pytest.mark.parametrize('delete_last_contributing', (False, True))
def test_review_settings_category_deletion_keeps_contributing_category(
    client, event, reviewer, exporter, categories, mocker,
    django_capture_on_commit_callbacks, delete_last_contributing,
):
    """Deleting the last contributing category must roll back scores and phase changes."""
    with scope(event=event):
        main, relevance = categories
        relevance.is_independent = delete_last_contributing
        relevance.save()
        review = create_review(event, reviewer, categories, 'A talk', (1, 2))
        original_score = review.score
        original_score_ids = set(review.scores.values_list('pk', flat=True))
        original_categories = list(event.score_categories.order_by('pk').values_list('pk', 'weight', 'is_independent'))
        phase = event.review_phases.order_by('position').first()
        original_phase_name = phase.name
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['scores-0-DELETE'] = 'on'
        data['phase-0-name'] = 'Updated phase'
        recalculate = mocker.patch('eventyay.orga.views.event.recalculate_all_review_scores.apply_async')

        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(event.orga_urls.review_settings, data)
            recalculate.assert_not_called()

        phase.refresh_from_db()
        review.refresh_from_db()
        if delete_last_contributing:
            assert response.status_code == 200
            assert b'You need to keep at least one non-independent score category!' in response.content
            assert list(event.score_categories.order_by('pk').values_list('pk', 'weight', 'is_independent')) == (
                original_categories
            )
            assert phase.name == original_phase_name
            assert set(review.scores.values_list('pk', flat=True)) == original_score_ids
            assert review.score == original_score
            recalculate.assert_not_called()
        else:
            assert response.status_code == 302
            assert not event.score_categories.filter(pk=main.pk).exists()
            assert event.score_categories.filter(is_independent=False).exists()
            assert phase.name == 'Updated phase'
            assert review.score == Decimal('2.00')
            recalculate.assert_called_once_with(kwargs={'event_id': event.pk}, ignore_result=True)


@pytest.mark.django_db
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
def test_review_settings_outer_rollback_discards_recalculation(
    client, event, reviewer, exporter, categories, mocker, django_capture_on_commit_callbacks
):
    """Rolling back after the handler returns must discard its task and score updates."""
    with scope(event=event):
        review = create_review(event, reviewer, categories, 'A talk', (1, 2))
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['scores-0-is_independent'] = 'on'
        recalculate = mocker.patch('eventyay.orga.views.event.recalculate_all_review_scores.apply_async')

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            with transaction.atomic():
                response = client.post(event.orga_urls.review_settings, data)
                assert response.status_code == 302
                recalculate.assert_not_called()
                transaction.set_rollback(True)

        assert callbacks == []
        recalculate.assert_not_called()
        main = categories[0]
        main.refresh_from_db()
        review.refresh_from_db()
        assert not main.is_independent and main.weight == 1
        assert review.score == Decimal('3.00')


@pytest.mark.django_db
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
def test_review_settings_broker_failure_keeps_successful_save(
    client, event, reviewer, exporter, categories, mocker, django_capture_on_commit_callbacks, caplog
):
    """Log a failed post-commit dispatch without reporting a saved configuration as rejected."""
    with scope(event=event):
        review = create_review(event, reviewer, categories, 'A talk', (1, 2))
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['scores-0-is_independent'] = 'on'
        recalculate = mocker.patch(
            'eventyay.orga.views.event.recalculate_all_review_scores.apply_async',
            side_effect=BrokerError('Broker unavailable'),
        )

        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(event.orga_urls.review_settings, data)
            recalculate.assert_not_called()

        assert response.status_code == 302
        main = categories[0]
        main.refresh_from_db()
        review.refresh_from_db()
        assert main.is_independent and main.weight == 0
        assert review.score == Decimal('2.00')
        recalculate.assert_called_once_with(kwargs={'event_id': event.pk}, ignore_result=True)
        assert 'Broker unavailable' in caplog.text


class TestConcurrentReviewSettings(TransactionTestCase):
    """Keep PostgreSQL cleanup cascading across the legacy tables used by this request."""

    available_apps = [app.name for app in apps.get_app_configs()]

    @pytest.fixture(autouse=True)
    def bind_test_fixtures(self, client, mocker, request):
        """Make the existing pytest helpers available to the Django transaction test."""
        self.client = client
        self.mocker = mocker
        self.fixture_request = request

    @pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row-lock contention.')
    @override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
    def test_concurrent_review_settings_wait_before_validating(self):
        """A competing save must wait for the current event's scoring transaction before validation."""
        client, mocker, request = self.client, self.mocker, self.fixture_request
        mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
        event = request.getfixturevalue('event')
        exporter = request.getfixturevalue('exporter')
        categories = request.getfixturevalue('categories')
        with scope(event=event):
            client.force_login(exporter)
            data = review_settings_data(client, event)
            data['scores-1-is_independent'] = 'on'
            mocker.patch('eventyay.orga.views.event.recalculate_all_review_scores.apply_async')
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    'error, expected_messages',
    [
        pytest.param(ValidationError('Cannot save scoring.'), ['Cannot save scoring.'], id='single'),
        pytest.param(
            ValidationError('Invalid category: %(name)s', params={'name': 'Relevance'}),
            ['Invalid category: Relevance'],
            id='single-with-params',
        ),
        pytest.param(
            ValidationError(['First validation error.', 'Second validation error.']),
            ['First validation error.', 'Second validation error.'],
            id='list',
        ),
        pytest.param(
            ValidationError({'weight': ['Invalid weight.'], '__all__': ['Invalid scoring configuration.']}),
            ['Invalid weight.', 'Invalid scoring configuration.'],
            id='dictionary',
        ),
    ],
)
@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
def test_review_settings_displays_all_validation_error_formats(
    client, event, exporter, mocker, error, expected_messages
):
    """Reject validation errors safely while rolling back earlier phase changes."""
    with scope(event=event):
        phase = event.review_phases.order_by('position').first()
        phase_name = phase.name
        client.force_login(exporter)
        data = review_settings_data(client, event)
        data['phase-0-name'] = 'This phase change must be rolled back'
        mocker.patch('eventyay.orga.views.event.EventReviewSettings.save_scores', side_effect=error)
        recalculate = mocker.patch('eventyay.orga.views.event.recalculate_all_review_scores.apply_async')

        response = client.post(event.orga_urls.review_settings, data)

        assert response.status_code == 200
        for message in expected_messages:
            assert message in response.content.decode()
        phase.refresh_from_db()
        assert phase.name == phase_name
        recalculate.assert_not_called()
