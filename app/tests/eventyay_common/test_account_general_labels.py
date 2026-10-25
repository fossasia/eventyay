import re

import pytest
from django.urls import reverse

from eventyay.base.models import User

STATIC_HEADINGS = [
    'Notifications',
    'Email Address',
    'Two-factor authentication',
    'Authorized applications',
    'Account history',
]


@pytest.mark.django_db
@pytest.mark.parametrize('heading', STATIC_HEADINGS)
def test_account_general_static_headings_are_not_labels(client, heading):
    user = User.objects.create_user(email='account_labels@example.com', password='password123')
    client.force_login(user)

    response = client.get(reverse('eventyay_common:account.general'))
    assert response.status_code == 200
    html = response.content.decode('utf-8')

    assert f"<div class='col-md-3 control-label'>{heading}</div>" in html
    assert not re.search(rf'<label[^>]*>\s*{re.escape(heading)}\s*</label>', html)
