import pytest
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
def test_video_admin_requires_authenticated_staff(client):
    response = client.get(reverse("eventyay_admin:video_admin:index"))

    assert response.status_code == 302
    assert "/control/auth/login/" in response.url


@pytest.mark.django_db
def test_video_admin_rejects_regular_users(authenticated_client):
    response = authenticated_client.get(reverse("eventyay_admin:video_admin:index"))

    assert response.status_code == 302
    assert "/control/auth/login/" in response.url


@pytest.mark.django_db
def test_video_admin_rejects_control_token(client):
    with override_settings(CONTROL_SECRET="video-admin-secret"):
        response = client.get(
            reverse("eventyay_admin:video_admin:index"),
            {"control_token": "video-admin-secret"},
        )

    assert response.status_code == 302
    assert "/control/auth/login/" in response.url


@pytest.mark.django_db
def test_video_admin_allows_staff_and_same_origin_frame(staff_client):
    response = staff_client.get(reverse("eventyay_admin:video_admin:index"))

    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
