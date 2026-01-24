import pytest
from django_scopes import scope

@pytest.mark.django_db
def test_orga_can_view_submission_content_and_questions(orga_client, submission, answer):
    """
    Test that an organizer can view the submission content page (ReadView).
    This view should include the submission questions and answers in the context.
    """
    response = orga_client.get(submission.orga_urls.base, follow=True)
    assert response.status_code == 200
    assert submission.title in response.text
    assert answer.answer in response.text
    assert "questions" in response.context
    # The 'questions' context variable contains answers, odd naming but matching the view code
    # ctx['questions'] = submission.answers.all()...
    assert answer in response.context["questions"]


@pytest.mark.django_db
def test_reviewer_can_view_submission_content(review_client, submission, answer):
    """
    Test that a reviewer can view the submission content page.
    Reviewers should also see the answers.
    """
    response = review_client.get(submission.orga_urls.base, follow=True)
    assert response.status_code == 200
    assert submission.title in response.text
    assert answer.answer in response.text


@pytest.mark.django_db
def test_user_cannot_view_submission_content_without_permission(client, submission):
    """
    Test that an unauthenticated user or user without permission is redirected.
    """
    response = client.get(submission.orga_urls.base, follow=True)
    # Checks for redirect to login page
    assert response.status_code == 200
    assert "login" in response.request["PATH_INFO"] or "login" in response.redirect_chain[0][0]
