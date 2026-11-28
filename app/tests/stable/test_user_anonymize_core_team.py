import time

import pytest
from django.urls import reverse

from eventyay.base.models import User
from eventyay.base.models.auth import StaffSession
from eventyay.base.services.organizer_creation import create_core_team


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def site_url(settings):
    settings.SITE_URL = 'https://testserver'


@pytest.fixture
def admin_client(client):
    admin = User.objects.create_user('admin@example.com', 'admin', is_staff=True)
    client.force_login(admin)
    session = client.session
    session['eventyay_auth_login_time'] = int(time.time())
    session.save()
    StaffSession.objects.create(user=admin, date_start=admin.date_joined, session_key=session.session_key)
    return client


def anonymize(client, user):
    return client.post(reverse('eventyay_admin:admin.users.anonymize', kwargs={'id': user.pk}), follow=True)


def test_last_active_core_member_cannot_be_anonymized(admin_client, organizer):
    owner = User.objects.create_user('owner@example.com', 'owner')
    create_core_team(organizer, owner)
    response = anonymize(admin_client, owner)
    owner.refresh_from_db()
    assert owner.is_active and owner.email == 'owner@example.com'
    assert 'cannot remove the last active member of the Core Organizing Team' in response.content.decode()


def test_core_member_can_be_anonymized_while_another_active_member_remains(admin_client, organizer):
    owner = User.objects.create_user('owner@example.com', 'owner')
    second = User.objects.create_user('second@example.com', 'second')
    team = create_core_team(organizer, owner)
    team.members.add(second)
    anonymize(admin_client, owner)
    owner.refresh_from_db()
    assert not owner.is_active and owner.email.endswith('@disabled.eventyay.com')


def test_user_outside_the_core_team_can_be_anonymized(admin_client):
    user = User.objects.create_user('someone@example.com', 'someone')
    anonymize(admin_client, user)
    user.refresh_from_db()
    assert not user.is_active
