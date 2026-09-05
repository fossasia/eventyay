from types import SimpleNamespace

import pytest
from django import forms

from eventyay.api.serializers.feedback import (
    AuthorSerializer,
    FeedbackReplySerializer,
    FeedbackSerializer,
)
from eventyay.base.models import Feedback
from eventyay.submission.forms.feedback import FeedbackForm


def test_author_serializer_uses_display_name_and_avatar_url():
    user = SimpleNamespace(
        code='speaker-1',
        get_display_name=lambda: 'Jane Speaker',
        avatar_url='https://example.com/avatar.png',
    )
    data = AuthorSerializer(user).data
    assert data == {
        'code': 'speaker-1',
        'name': 'Jane Speaker',
        'avatar': 'https://example.com/avatar.png',
    }


def test_feedback_rating_properties():
    # Test valid ratings mapped to emoji and labels
    for rating, (expected_emoji, expected_label) in Feedback.EMOJI_RATING_MAP.items():
        fb = Feedback(rating=rating)
        assert fb.rating_emoji == expected_emoji
        assert fb.rating_label == str(expected_label)

    # Test unrated / None rating
    fb_none = Feedback(rating=None)
    assert fb_none.rating_emoji == ''
    assert fb_none.rating_label == ''

    # Test out-of-range rating
    fb_invalid = Feedback(rating=99)
    assert fb_invalid.rating_emoji == ''
    assert fb_invalid.rating_label == ''


def test_feedback_serializer_includes_rating_fields():
    fb = Feedback(id=1, rating=5, review='Superb!', status='published', is_public=True)
    fb.author = None
    fb.cached_replies = []
    serializer = FeedbackSerializer(fb)
    data = serializer.data
    assert data['rating'] == 5
    assert data['rating_emoji'] == '😍'
    assert data['rating_label'] == 'Excellent'


def test_feedback_reply_serializer_includes_rating_fields():
    reply = Feedback(id=2, rating=None, review='Reply text', status='published', is_public=True)
    reply.author = None
    serializer = FeedbackReplySerializer(reply)
    data = serializer.data
    assert data['rating'] is None
    assert data['rating_emoji'] == ''
    assert data['rating_label'] == ''


def test_feedback_form_clean_rating():
    talk = SimpleNamespace(
        speakers=SimpleNamespace(all=lambda: [], count=lambda: 0),
        event=SimpleNamespace(feature_flags={}),
    )
    # Valid ratings 1 through 5
    for r in (1, 2, 3, 4, 5):
        form = FeedbackForm(talk=talk)
        form.cleaned_data = {'rating': r}
        assert form.clean_rating() == r

    # Invalid ratings
    for invalid in (0, 6, -1, 'invalid'):
        form = FeedbackForm(talk=talk)
        form.cleaned_data = {'rating': invalid}
        with pytest.raises(forms.ValidationError):
            form.clean_rating()


def test_feedback_form_clean_clears_rating_on_reply():
    talk = SimpleNamespace(
        speakers=SimpleNamespace(all=lambda: [], count=lambda: 0),
        event=SimpleNamespace(feature_flags={}),
    )
    form = FeedbackForm(talk=talk)
    form.cleaned_data = {'parent': 42, 'rating': 5}
    cleaned = form.clean()
    assert cleaned['rating'] is None


def test_feedback_model_clean_rating_validation():
    from django.core.exceptions import ValidationError as DjangoValidationError
    fb_valid = Feedback(rating=5)
    fb_valid.clean()

    fb_invalid = Feedback(rating=6)
    with pytest.raises(DjangoValidationError):
        fb_invalid.clean()

    fb_reply = Feedback(parent=fb_valid, rating=4)
    fb_reply.clean()
    assert fb_reply.rating is None


def test_feedback_serializer_validates_rating_range():
    from rest_framework.exceptions import ValidationError as DRFValidationError
    serializer = FeedbackSerializer()
    assert serializer.validate_rating(5) == 5
    with pytest.raises(DRFValidationError):
        serializer.validate_rating(6)
    with pytest.raises(DRFValidationError):
        serializer.validate_rating(0)


