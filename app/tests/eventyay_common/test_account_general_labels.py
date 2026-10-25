import pytest
from bs4 import BeautifulSoup
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
    doc = BeautifulSoup(response.content, 'lxml')

    assert not [label for label in doc.find_all('label') if heading in label.get_text(strip=True)]
    assert [
        div
        for div in doc.find_all('div', class_='col-md-3')
        if 'control-label' in div.get('class', []) and div.get_text(strip=True) == heading
    ]
