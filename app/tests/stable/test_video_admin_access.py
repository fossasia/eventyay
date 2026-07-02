from urllib.parse import parse_qs, urlparse

import pytest
from django.test import override_settings
from django.urls import reverse


def assert_redirects_to_login(response):
    assert response.status_code == 302
    parsed_url = urlparse(response.url)
    assert (
        parsed_url.path.startswith("/login")
        or parsed_url.path.startswith("/control/auth/login")
        or parsed_url.path.startswith("/common/login")
    )
    assert parse_qs(parsed_url.query).get("next") == ["/admin/video/"]


@pytest.mark.django_db
def test_video_admin_requires_authenticated_staff(client):
    response = client.get(reverse("eventyay_admin:video_admin:index"))

    assert_redirects_to_login(response)


@pytest.mark.django_db
def test_video_admin_rejects_regular_users(authenticated_client):
    response = authenticated_client.get(reverse("eventyay_admin:video_admin:index"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_video_admin_rejects_control_token(client):
    with override_settings(CONTROL_SECRET="video-admin-secret"):
        response = client.get(
            reverse("eventyay_admin:video_admin:index"),
            {"control_token": "video-admin-secret"},
        )

    assert_redirects_to_login(response)


@pytest.mark.django_db
def test_video_admin_allows_staff_and_same_origin_frame(staff_client):
    response = staff_client.get(reverse("eventyay_admin:video_admin:index"))

    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
