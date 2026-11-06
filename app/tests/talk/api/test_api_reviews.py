import json
from decimal import Decimal

import pytest
from django_scopes import scope

from eventyay.api.serializers.review import ReviewSerializer
from eventyay.base.models import (
    Answer,
    Review,
    ReviewScore,
    ReviewScoreCategory,
    Submission,
)


@pytest.fixture
def review_score_category(event):
    return ReviewScoreCategory.objects.create(event=event, name="Impact", weight=1)


@pytest.fixture
def review_score_value_positive(review_score_category):
    return ReviewScore.objects.create(
        category=review_score_category, value=Decimal("2.0"), label="Good"
    )


@pytest.fixture
def review_score_value_negative(review_score_category):
    return ReviewScore.objects.create(
        category=review_score_category, value=Decimal("-1.0"), label="Bad"
    )


@pytest.mark.django_db
def test_review_serializer(review):
    with scope(event=review.event):
        data = ReviewSerializer(review).data
        assert set(data.keys()) == {
            "id",
            "answers",
            "submission",
            "user",
            "text",
            "score",
            "scores",
        }
        assert data["submission"] == review.submission.code
        assert data["user"] == review.user.code
        assert data["answers"] == []


@pytest.mark.django_db
def test_anon_cannot_see_reviews(client, event, review):
    response = client.get(event.api_urls.reviews, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_reviews(client, orga_user_token, event, review):
    response = client.get(
        event.api_urls.reviews + "?expand=answers",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1


@pytest.mark.django_db
def test_orga_can_see_expanded_reviews(
    client,
    orga_user_token,
    event,
    review,
    track,
    review_score_value_positive,
    review_question,
):
    with scope(event=event):
        review.submission.track = track
        review.scores.add(review_score_value_positive)
        review.submission.save()
        speaker = review.submission.speakers.all().first()
        submission_type = review.submission.submission_type
        user = review.user
        category = review_score_value_positive.category
        Answer.objects.create(review=review, question=review_question, answer="text!")

    params = ",".join(
        [
            "user",
            "scores.category",
            "submission.speakers",
            "submission.track",
            "submission.submission_type",
            "answers",
        ]
    )
    response = client.get(
        f"{event.api_urls.reviews}?expand={params}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1
    data = content["results"][0]
    assert data["submission"]["code"] == review.submission.code
    assert data["submission"]["speakers"][0]["code"] == speaker.code
    assert data["submission"]["track"]["name"]["en"] == track.name
    assert data["submission"]["submission_type"]["name"]["en"] == submission_type.name
    assert data["user"]["code"] == user.code
    assert data["user"]["fullname"] == user.fullname
    assert data["scores"][0]["category"]["name"]["en"] == category.name
    assert data["answers"][0]["answer"] == "text!"


@pytest.mark.django_db
def test_orga_cannot_see_reviews_of_deleted_submission(
    client, orga_user_token, event, review
):
    review.submission.state = "deleted"
    review.submission.save()
    response = client.get(
        event.api_urls.reviews,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 0


@pytest.mark.django_db
def test_reviewer_can_see_reviews(
    client, review_user_token, event, review, other_review
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
    response = client.get(
        event.api_urls.reviews,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200, content
    assert len(content["results"]) == 2, content


@pytest.mark.django_db
def test_reviewer_can_see_reviews_by_track(
    client,
    review_user_token,
    review_user,
    event,
    review,
    other_review,
    track,
    other_track,
    slot,  # Make sure this also applies once there is a public schedule!
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
        review.submission.track = track
        review.submission.save()
        other_review.submission.track = other_track
        other_review.submission.save()
        review_user.teams.filter(is_reviewer=True).first().limit_tracks.add(track)

    response = client.get(
        event.api_urls.reviews,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1, content


@pytest.mark.django_db
def test_reviewer_can_filter_by_submission(
    client, review_user_token, event, review, other_review
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
    response = client.get(
        event.api_urls.reviews,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 2

    response = client.get(
        event.api_urls.reviews + f"?submission={review.submission.code}",
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1, content
    returned = content["results"][0]
    assert returned["submission"] == review.submission.code, content
    assert returned["submission"] != other_review.submission.code, content


@pytest.mark.django_db
def test_reviewer_can_filter_by_speaker_with_multiple_submissions(
    client, review_user_token, review_user, event, review, submission, speaker
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
        second_submission = Submission.objects.create(
            title="Second talk by the same speaker",
            event=event,
            submission_type=event.cfp.default_type,
            description="Description",
            abstract="Abstract",
            notes="Notes",
            content_locale="en",
        )
        second_submission.speakers.add(speaker)
        Review.objects.create(
            score=1,
            submission=second_submission,
            user=review_user,
            text="Second review",
        )
        speaker_code = speaker.code
        expected_codes = [submission.code, second_submission.code]

    response = client.get(
        event.api_urls.reviews + f"?speaker={speaker_code}",
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    returned_codes = sorted(r["submission"] for r in content["results"])
    assert returned_codes == sorted(expected_codes), content


@pytest.mark.django_db
def test_reviewer_cannot_see_review_to_own_talk(
    client, review_user_token, review_user, event, review, other_review
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
        other_review.submission.speakers.add(review_user)
    response = client.get(
        event.api_urls.reviews,
        follow=True,
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content["results"]) == 1, content


@pytest.mark.django_db
def test_reviewer_can_create_review(
    client, review_user_token, event, submission, review_user
):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        assert not Review.objects.filter(
            submission=submission, user=review_user
        ).exists()
        url = event.api_urls.reviews
        data = {"submission": submission.code, "text": "This is a new review."}

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 201, response.text

    with scope(event=event):
        new_review = Review.objects.get(submission=submission, user=review_user)
        assert new_review.text == data["text"]
        assert new_review.score is None


@pytest.mark.django_db
def test_reviewer_can_create_review_with_scores(
    client,
    review_user_token,
    event,
    submission,
    review_user,
    review_score_category,
    review_score_value_positive,
):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        url = event.api_urls.reviews
        data = {
            "submission": submission.code,
            "text": "This is a new review with scores.",
            "scores": [review_score_value_positive.pk],
        }

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 201, response.text

    with scope(event=event):
        new_review = Review.objects.get(submission=submission, user=review_user)
        assert new_review.text == data["text"]
        assert new_review.scores.count() == 1
        assert new_review.scores.first() == review_score_value_positive
        assert (
            new_review.score
            == review_score_value_positive.value * review_score_category.weight
        )


@pytest.mark.django_db
def test_reviewer_cannot_create_duplicate_review(
    client, review_user_token, event, review
):
    with scope(event=event):
        url = event.api_urls.reviews
        data = {"submission": review.submission.code, "text": "Duplicate review."}

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 400, response.text
    content = json.loads(response.text)
    assert "You have already reviewed this submission." in content["submission"]


@pytest.mark.django_db
def test_reviewer_cannot_create_review_for_own_submission(
    client, review_user_token, event, submission, review_user
):
    with scope(event=event):
        submission.speakers.add(review_user)
        submission.save()
        url = event.api_urls.reviews
        data = {"submission": submission.code, "text": "Review for my own talk."}

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 400, response.text
    content = json.loads(response.text)
    assert content["submission"]


@pytest.mark.django_db
def test_reviewer_cannot_create_review_if_phase_disallows(
    client, review_user_token, event, submission
):
    with scope(event=event):
        phase = event.active_review_phase
        phase.can_review = False
        phase.save()
        url = event.api_urls.reviews
        data = {"submission": submission.code, "text": "Review when phase closed."}

    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text


@pytest.mark.django_db
def test_anonymous_cannot_create_review(client, event, submission):
    url = event.api_urls.reviews
    data = {"submission": submission.code, "text": "Anonymous review."}
    response = client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == 401, response.text


@pytest.mark.django_db
def test_reviewer_can_update_own_review_text(client, review_user_token, event, review):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        url = event.api_urls.reviews + f"{review.pk}/"
        new_text = "This is an updated review text."
        data = {"text": new_text}

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 200, response.text

    with scope(event=event):
        review.refresh_from_db()
        assert review.text == new_text


@pytest.mark.django_db
def test_reviewer_can_update_own_review_scores(
    client,
    review_user_token,
    event,
    review,
    review_score_category,
    review_score_value_positive,
    review_score_value_negative,
):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        review.scores.add(review_score_value_negative)
        review.save()
        initial_score = review.score

        url = event.api_urls.reviews + f"{review.pk}/"
        data = {"scores": [review_score_value_positive.pk]}

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 200, response.text

    with scope(event=event):
        review.refresh_from_db()
        assert review.scores.count() == 1
        assert review.scores.first() == review_score_value_positive
        assert review.score != initial_score
        assert (
            review.score
            == review_score_value_positive.value * review_score_category.weight
        )


@pytest.mark.django_db
def test_reviewer_cannot_add_multiple_scores_same_category(
    client,
    review_user_token,
    event,
    review,
    review_score_category,
    review_score_value_positive,
    review_score_value_negative,
):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        review.scores.add(review_score_value_negative)
        review.save()
        initial_score = review.score

        url = event.api_urls.reviews + f"{review.pk}/"
        data = {
            "scores": [review_score_value_positive.pk, review_score_value_negative.pk]
        }

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 400, response.text

    with scope(event=event):
        review.refresh_from_db()
        assert review.scores.count() == 1
        assert review.scores.first() == review_score_value_negative
        assert review.score == initial_score


@pytest.mark.django_db
def test_reviewer_cannot_update_other_review(
    client, review_user_token, event, other_review
):
    with scope(event=event):
        url = event.api_urls.reviews + f"{other_review.pk}/"
        data = {"text": "Trying to update someone else's review."}

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text


@pytest.mark.django_db
def test_reviewer_cannot_update_review_if_phase_disallows(
    client, review_user_token, event, review
):
    with scope(event=event):
        phase = event.active_review_phase
        phase.can_review = False
        phase.save()
        url = event.api_urls.reviews + f"{review.pk}/"
        data = {"text": "Update when phase closed."}

    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {review_user_token.token}"},
    )
    assert response.status_code == 403, response.text


@pytest.mark.django_db
def test_anonymous_cannot_update_review(client, event, review):
    url = event.api_urls.reviews + f"{review.pk}/"
    data = {"text": "Anonymous update."}
    response = client.patch(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == 404, response.text


@pytest.mark.django_db
def test_reviewer_can_delete_own_review(client, review_user_token, event, review):
    with scope(event=event):
        assert event.active_review_phase.can_review is True
        review_pk = review.pk
        assert Review.objects.filter(pk=review_pk).exists()
        url = event.api_urls.reviews + f"{review_pk}/"

    response = client.delete(
        url, headers={"Authorization": f"Token {review_user_token.token}"}
    )
    assert response.status_code == 204, response.text

    with scope(event=event):
        assert not Review.objects.filter(pk=review_pk).exists()


@pytest.mark.django_db
def test_reviewer_cannot_delete_other_review(
    client, review_user_token, event, other_review
):
    with scope(event=event):
        assert Review.objects.filter(pk=other_review.pk).exists()
        url = event.api_urls.reviews + f"{other_review.pk}/"

    response = client.delete(
        url, headers={"Authorization": f"Token {review_user_token.token}"}
    )
    assert response.status_code == 403, response.text

    with scope(event=event):
        assert Review.objects.filter(pk=other_review.pk).exists()


@pytest.mark.django_db
def test_reviewer_cannot_delete_review_if_phase_disallows(
    client, review_user_token, event, review
):
    with scope(event=event):
        phase = event.active_review_phase
        phase.can_review = False
        phase.save()
        assert Review.objects.filter(pk=review.pk).exists()
        url = event.api_urls.reviews + f"{review.pk}/"

    response = client.delete(
        url, headers={"Authorization": f"Token {review_user_token.token}"}
    )
    assert response.status_code == 403, response.text

    with scope(event=event):
        assert Review.objects.filter(pk=review.pk).exists()


@pytest.mark.django_db
def test_anonymous_cannot_delete_review(client, event, review):
    url = event.api_urls.reviews + f"{review.pk}/"
    response = client.delete(url)
    assert response.status_code == 404, response.text


@pytest.mark.django_db
def test_reviewer_cannot_enumerate_inaccessible_submission_or_speaker(
    client,
    review_user_token,
    review_user,
    event,
    review,
    other_review,
    track,
    other_track,
):
    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = "always"
        event.active_review_phase.save()
        review.submission.track = track
        review.submission.save()
        other_review.submission.track = other_track
        other_review.submission.save()
        review_user.teams.filter(is_reviewer=True).first().limit_tracks.add(track)

        accessible_sub_code = review.submission.code
        inaccessible_sub_code = other_review.submission.code
        accessible_speaker_code = review.submission.speakers.first().code
        inaccessible_speaker_code = other_review.submission.speakers.first().code

    headers = {"Authorization": f"Token {review_user_token.token}"}

    resp = client.get(event.api_urls.reviews + f"?submission={accessible_sub_code}", follow=True, headers=headers)
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    assert len(content["results"]) == 1
    assert content["results"][0]["submission"] == accessible_sub_code

    resp = client.get(event.api_urls.reviews + f"?speaker={accessible_speaker_code}", follow=True, headers=headers)
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    assert len(content["results"]) == 1
    assert content["results"][0]["submission"] == accessible_sub_code

    resp = client.get(event.api_urls.reviews + f"?submission={inaccessible_sub_code}", follow=True, headers=headers)
    assert resp.status_code == 400
    assert "submission" in resp.json()

    resp = client.get(event.api_urls.reviews + f"?speaker={inaccessible_speaker_code}", follow=True, headers=headers)
    assert resp.status_code == 400
    assert "speaker" in resp.json()


@pytest.mark.django_db
def test_organizer_can_filter_reviews_by_submission_and_speaker(
    client, orga_user_token, event, review
):
    with scope(event=event):
        sub_code = review.submission.code
        speaker_code = review.submission.speakers.first().code

    headers = {"Authorization": f"Token {orga_user_token.token}"}
    resp = client.get(event.api_urls.reviews + f"?submission={sub_code}", follow=True, headers=headers)
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    assert len(content["results"]) == 1
    assert content["results"][0]["submission"] == sub_code

    resp = client.get(event.api_urls.reviews + f"?speaker={speaker_code}", follow=True, headers=headers)
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    assert len(content["results"]) == 1
    assert content["results"][0]["submission"] == sub_code


@pytest.mark.django_db
def test_review_search_by_submission_title_and_reviewer_name(
    client, orga_user_token, event, review, other_review
):
    with scope(event=event):
        review.submission.title = "Unique Quantum Review Title"
        review.submission.save()
        other_review.submission.title = "Completely Other Title"
        other_review.submission.save()
        review.user.fullname = "SpecificReviewerAlpha"
        review.user.save()

    headers = {"Authorization": f"Token {orga_user_token.token}"}

    # Search by submission title
    resp = client.get(event.api_urls.reviews + "?search=Quantum", follow=True, headers=headers)
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    assert len(content["results"]) == 1
    assert content["results"][0]["submission"] == review.submission.code

    # Search by reviewer fullname
    resp = client.get(event.api_urls.reviews + "?search=SpecificReviewerAlpha", follow=True, headers=headers)
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    assert len(content["results"]) == 1
    assert content["results"][0]["id"] == review.pk


@pytest.mark.django_db
def test_review_filter_init_supports_explicit_event_and_fallback(event, orga_user_token, other_event, other_submission):
    from eventyay.api.filters.review import ReviewFilter

    # 1. Call with event=event directly (no request) -> missing user yields empty choices
    filt = ReviewFilter(event=event)
    assert filt.filters['user'].queryset.count() == 0
    assert filt.filters['submission'].queryset.count() == 0

    # 2. Call without event or request: qs is empty, no cross-event review leakage
    filt_empty = ReviewFilter()
    assert filt_empty.qs.count() == 0
    assert filt_empty.filters['submission'].queryset.count() == 0
    assert filt_empty.filters['user'].queryset.count() == 0
    assert filt_empty.filters['speaker'].queryset.count() == 0

    # 3. Explicitly empty visible_submissions does not fall through
    class MockView:
        visible_submissions = Submission.objects.none()

    class MockUser:
        is_anonymous = False
        is_authenticated = True
        pk = 99999

    class MockRequest:
        def __init__(self, ev):
            self.event = ev
            self.user = MockUser()
            self.parser_context = {'view': MockView()}

    filt_mock = ReviewFilter(request=MockRequest(event))
    assert filt_mock.filters['submission'].queryset.count() == 0


@pytest.mark.django_db
def test_review_filter_rejects_submission_from_other_event(
    client, orga_user_token, event, other_event
):
    with scope(event=other_event):
        foreign_sub = Submission.objects.create(
            event=other_event,
            title="Foreign Submission",
            submission_type=other_event.cfp.default_type,
        )

    headers = {"Authorization": f"Token {orga_user_token.token}"}
    # Attempting to filter by another event's submission code produces 400
    resp = client.get(
        event.api_urls.reviews + f"?submission={foreign_sub.code}",
        follow=True,
        headers=headers,
    )
    assert resp.status_code == 400
    assert "submission" in resp.json()


@pytest.mark.django_db
def test_review_filter_anonymous_user_without_view_has_empty_submissions(event):
    from django.contrib.auth.models import AnonymousUser
    from eventyay.api.filters.review import ReviewFilter

    class MockRequestWithoutView:
        def __init__(self, ev):
            self.event = ev
            self.user = AnonymousUser()
            self.parser_context = {}

    filt = ReviewFilter(request=MockRequestWithoutView(event), event=event)
    assert filt.filters['submission'].queryset.count() == 0
    assert filt.filters['speaker'].queryset.count() == 0


@pytest.mark.django_db
def test_review_filter_submission_choice_with_multiple_related_rows_no_duplicate_error(
    client, orga_user_token, event, review, speaker, other_speaker
):
    from eventyay.api.filters.review import ReviewFilter

    with scope(event=event):
        # Attach multiple speakers to create multi-table join multiplicity
        sub = review.submission
        sub.speakers.add(speaker, other_speaker)
        sub.save()

    # Instantiate filter directly
    class MockRequest:
        def __init__(self, ev, user):
            self.event = ev
            self.user = user
            self.parser_context = {}

    req = MockRequest(event, orga_user_token.user)
    filt = ReviewFilter(request=req, event=event)

    # 1. Verify submission count for this code is exactly 1 (no duplicate rows)
    sub_qs = filt.filters['submission'].queryset
    assert sub_qs.filter(code=sub.code).count() == 1
    # 2. Verify .get() works cleanly without MultipleObjectsReturned
    resolved_sub = sub_qs.get(code=sub.code)
    assert resolved_sub.pk == sub.pk

    # 3. Verify API GET request with ?submission=<code > validates and returns 200
    headers = {"Authorization": f"Token {orga_user_token.token}"}
    resp = client.get(
        event.api_urls.reviews + f"?submission={sub.code}",
        follow=True,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    assert len(content["results"]) == 1
    assert content["results"][0]["submission"] == sub.code


@pytest.mark.django_db
def test_review_filter_speaker_choice_anonymised_phase(
    client, orga_user_token, review_user, event, review, speaker
):
    from eventyay.api.filters.review import ReviewFilter

    with scope(event=event):
        event.active_review_phase.can_see_speaker_names = False
        event.active_review_phase.save()
        team = review_user.teams.first()
        team.all_events = True
        team.save()

    class MockRequest:
        def __init__(self, ev, user):
            self.event = ev
            self.user = user
            self.parser_context = {}

    req_rev = MockRequest(event, review_user)
    filt_rev = ReviewFilter(request=req_rev, event=event)
    assert filt_rev.filters['speaker'].queryset.count() == 0

    req_orga = MockRequest(event, orga_user_token.user)
    filt_orga = ReviewFilter(request=req_orga, event=event)
    assert filt_orga.filters['speaker'].queryset.filter(pk=speaker.pk).exists()


@pytest.mark.django_db
def test_review_filter_anonymous_user_empty_choices(event, review):
    from django.contrib.auth.models import AnonymousUser
    from eventyay.api.filters.review import ReviewFilter

    class MockAnonRequest:
        def __init__(self, ev):
            self.event = ev
            self.user = AnonymousUser()
            self.parser_context = {}

    req_anon = MockAnonRequest(event)
    filt_anon = ReviewFilter(request=req_anon, event=event)
    assert filt_anon.filters['user'].queryset.count() == 0
    assert filt_anon.filters['submission'].queryset.count() == 0
    assert filt_anon.filters['speaker'].queryset.count() == 0

    filt_no_user = ReviewFilter(request=None, event=event)
    assert filt_no_user.filters['user'].queryset.count() == 0
    assert filt_no_user.filters['submission'].queryset.count() == 0
    assert filt_no_user.filters['speaker'].queryset.count() == 0

    # 3. Authenticated authorized user retains legitimate choices
    class MockAuthRequest:
        def __init__(self, ev, u):
            self.event = ev
            self.user = u
            self.parser_context = {}

    from eventyay.base.models import User
    filt_auth = ReviewFilter(request=MockAuthRequest(event, review.user), event=event)
    assert filt_auth.filters['user'].queryset.count() == event.reviewers.count()


@pytest.mark.django_db
def test_review_ordering_whitelist_and_speaker_leak_prevention(
    client, event, review_user, orga_user_token, submission
):
    from eventyay.base.models import Review, Submission

    with scope(event=event):
        event.active_review_phase.can_see_other_reviews = 'always'
        event.active_review_phase.can_see_speaker_names = False
        event.active_review_phase.save()

        sub2 = Submission.objects.create(
            event=event,
            title='Second Submission',
            state='submitted',
            submission_type=event.submission_types.first(),
        )
        # Create two reviews with distinct scores
        rev1 = Review.objects.create(
            submission=submission,
            user=review_user,
            text='Low score review',
            score=1,
        )
        rev2 = Review.objects.create(
            submission=sub2,
            user=review_user,
            text='High score review',
            score=5,
        )

    headers = {'Authorization': f'Token {orga_user_token.token}'}

    # 1. Allowed ordering by score ascending
    resp_asc = client.get(f'{event.api_urls.reviews}?ordering=score', follow=True, headers=headers)
    assert resp_asc.status_code == 200
    results_asc = resp_asc.json()['results']
    assert len(results_asc) >= 2
    scores_asc = [float(r['score']) for r in results_asc]
    assert scores_asc == sorted(scores_asc)

    # 2. Allowed ordering by score descending
    resp_desc = client.get(f'{event.api_urls.reviews}?ordering=-score', follow=True, headers=headers)
    assert resp_desc.status_code == 200
    results_desc = resp_desc.json()['results']
    scores_desc = [float(r['score']) for r in results_desc]
    assert scores_desc == sorted(scores_desc, reverse=True)

    # 3. Disallowed speaker-derived ordering is rejected/ignored by whitelist
    resp_disallowed = client.get(
        f'{event.api_urls.reviews}?ordering=submission__speakers__fullname',
        follow=True,
        headers=headers,
    )
    assert resp_disallowed.status_code == 200
    # Falls back to default ordering (pk ascending), not reordered by speaker
    pks = [r['id'] for r in resp_disallowed.json()['results']]
    assert pks == sorted(pks)
