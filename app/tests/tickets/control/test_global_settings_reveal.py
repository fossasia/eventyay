import pytest
from django.urls import reverse

from eventyay.base.models import User
from eventyay.base.settings import GlobalSettingsObject


@pytest.fixture
def admin_password():
    return 'adminpass123!'


@pytest.fixture
def admin_user(admin_password):
    user = User.objects.create_user('admin@example.com', admin_password)
    user.is_staff = True
    user.is_active = True
    user.save()
    return user


@pytest.fixture
def normal_user():
    user = User.objects.create_user('user@example.com', 'userpass123!')
    user.is_active = True
    user.save()
    return user


from eventyay.base.models.auth import StaffSession

@pytest.fixture
def staff_client(client, admin_user):
    client.force_login(admin_user)
    StaffSession.objects.create(user=admin_user, session_key=client.session.session_key)
    return client


@pytest.fixture
def normal_client(client, normal_user):
    client.force_login(normal_user)
    return client


@pytest.fixture
def reveal_url():
    return reverse('eventyay_admin:admin.global.settings.reveal_secret')


@pytest.mark.django_db
def test_reveal_secret_success(staff_client, admin_password, reveal_url):
    gs = GlobalSettingsObject()
    gs.settings.set('smtp_password', 'secret_value')

    response = staff_client.post(
        reveal_url,
        data={
            'key': 'smtp_password',
            'password': admin_password,
        },
    )
    assert response.status_code == 200
    assert response.json()['value'] == 'secret_value'


@pytest.mark.django_db
def test_reveal_secret_invalid_password(staff_client, reveal_url):
    gs = GlobalSettingsObject()
    gs.settings.set('smtp_password', 'secret_value')

    response = staff_client.post(
        reveal_url,
        data={
            'key': 'smtp_password',
            'password': 'wrongpassword',
        },
    )
    assert response.status_code == 403
    assert response.json()['error'] == 'invalid_password'


@pytest.mark.django_db
def test_reveal_secret_key_not_allowed(staff_client, admin_password, reveal_url):
    gs = GlobalSettingsObject()
    gs.settings.set('some_other_setting', 'secret_value')

    response = staff_client.post(
        reveal_url,
        data={
            'key': 'some_other_setting',
            'password': admin_password,
        },
    )
    assert response.status_code == 403
    assert response.json()['error'] == 'forbidden'


@pytest.mark.django_db
def test_reveal_secret_empty_value(staff_client, admin_password, reveal_url):
    gs = GlobalSettingsObject()
    gs.settings.delete('smtp_password')

    response = staff_client.post(
        reveal_url,
        data={
            'key': 'smtp_password',
            'password': admin_password,
        },
    )
    assert response.status_code == 404
    assert response.json()['error'] == 'not_set'


@pytest.mark.django_db
def test_reveal_secret_requires_staff(normal_client, admin_password, reveal_url):
    # A normal user without is_staff should be denied
    response = normal_client.post(
        reveal_url,
        data={
            'key': 'smtp_password',
            'password': admin_password,
        },
    )
    assert response.status_code in (302, 403)
