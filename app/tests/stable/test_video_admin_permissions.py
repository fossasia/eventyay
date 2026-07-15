import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_video_admin_bbb_list_requires_active_staff_session(staff_client):
    response = staff_client.get(reverse("eventyay_admin:video_admin:bbbserver.list"))

    assert response.status_code == 302
    assert reverse("control:user.sudo") in response["Location"]
