import pytest
from django_scopes import scope, scopes_disabled

from eventyay.base.models import User
from eventyay.base.models.auth import StaffSession


@pytest.fixture(params=(True, False), ids=('administrator', 'staff_only'))
def admin_mode_user(request, event):
    with scopes_disabled():
        user = User.objects.create_user(email='platform-admin@example.org', password='adminpassw0rd')
        user.is_staff = True
        user.is_administrator = request.param
        user.save()
    assert not user.teams.exists()
    return user


@pytest.fixture
def admin_mode_client(admin_mode_user, client):
    client.force_login(admin_mode_user)
    session = client.session
    session.save()
    StaffSession.objects.create(user=admin_mode_user, session_key=session.session_key)
    return client


@pytest.mark.django_db
def test_admin_mode_gets_speaker_autocomplete(admin_mode_client, event, speaker):
    response = admin_mode_client.get(event.orga_urls.base + 'speaker-autocomplete/', {'search': 'jane@speaker'})
    assert response.status_code == 200
    results = response.json()['results']
    assert [result['email'] for result in results] == [speaker.email]
    assert results[0]['name'] == speaker.fullname


@pytest.mark.django_db
def test_admin_mode_can_read_outbox(admin_mode_client, event, mail):
    response = admin_mode_client.get(event.orga_urls.outbox)
    assert response.status_code == 200
    assert mail.subject in response.text

    response = admin_mode_client.get(mail.urls.base)
    assert response.status_code == 200
    assert mail.subject in response.text


@pytest.mark.django_db
def test_admin_mode_can_submit_review(admin_mode_client, admin_mode_user, submission):
    with scope(event=submission.event):
        category = submission.event.score_categories.first()
        score = category.scores.filter(value=1).first()
    response = admin_mode_client.post(
        submission.orga_urls.reviews,
        follow=True,
        data={f'score_{category.id}': score.id, 'text': 'LGTM'},
    )
    assert response.status_code == 200
    with scope(event=submission.event):
        review = submission.reviews.get()
        assert review.user == admin_mode_user
        assert review.text == 'LGTM'
    response = admin_mode_client.get(submission.orga_urls.reviews)
    assert 'LGTM' in response.text


def _post_review(client, submission):
    with scope(event=submission.event):
        category = submission.event.score_categories.first()
        score = category.scores.filter(value=1).first()
    return client.post(
        submission.orga_urls.reviews,
        follow=True,
        data={f'score_{category.id}': score.id, 'text': 'LGTM'},
    )


@pytest.mark.django_db
def test_admin_mode_cannot_review_when_review_phase_closed(admin_mode_client, submission):
    with scope(event=submission.event):
        phase = submission.event.active_review_phase
        phase.can_review = False
        phase.save()
    _post_review(admin_mode_client, submission)
    with scope(event=submission.event):
        assert not submission.reviews.exists()


@pytest.mark.django_db
def test_admin_without_admin_mode_cannot_review(admin_mode_user, client, submission):
    client.force_login(admin_mode_user)
    _post_review(client, submission)
    with scope(event=submission.event):
        assert not submission.reviews.exists()
