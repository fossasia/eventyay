from decimal import Decimal

import pytest
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
def review(event, reviewer):
    with scope(event=event):
        submission = Submission.objects.create(
            title='A talk', event=event, submission_type=event.cfp.default_type
        )
        # The default category, named "Score" like the total score column
        main = event.score_categories.get()
        relevance = ReviewScoreCategory.objects.create(event=event, name='Relevance')
        review = Review.objects.create(submission=submission, user=reviewer, text='Good')
        review.scores.set(
            [
                ReviewScore.objects.create(category=main, value=1, label='Maybe'),
                ReviewScore.objects.create(category=relevance, value=2, label='High'),
            ]
        )
        review.save()
        return review


@pytest.mark.django_db
def test_review_export_has_total_and_per_category_scores(event, reviewer, review):
    with scope(event=event), translation.override('en'):
        form = ReviewExportForm(event=event, user=reviewer, data={})
        categories = {str(category.name): category for category in form.score_categories}
        fields = ['score', f'score_{categories["Score"].pk}', f'score_{categories["Relevance"].pk}']
        queryset = Review.objects.filter(pk=review.pk).prefetch_related('scores')

        (row,) = form.get_data(queryset, fields, [])

        assert row == {
            'Score': Decimal('3.00'),
            'Score in “Score”': Decimal('1.00'),
            'Score in “Relevance”': Decimal('2.00'),
        }


@pytest.mark.django_db
def test_review_export_skips_unselected_category_scores(event, reviewer, review):
    with scope(event=event), translation.override('en'):
        form = ReviewExportForm(event=event, user=reviewer, data={})
        queryset = Review.objects.filter(pk=review.pk).prefetch_related('scores')

        (row,) = form.get_data(queryset, ['score', 'text'], [])

        assert row == {'Score': Decimal('3.00'), 'Text': 'Good'}
