import pytest
from django.urls import reverse

from eventyay.base.models import User


def latest_action_type(user):
    return user.all_logentries.order_by('-datetime', '-id').values_list('action_type', flat=True).first()


@pytest.mark.django_db
def test_turning_notifications_off_logs_disabled(client):
    user = User.objects.create_user(email='notif_off@example.com', password='password123')
    client.force_login(user)
    assert user.notifications_send

    response = client.post(reverse('eventyay_common:account.notifications'), {'notifications_send': 'off'})

    assert response.status_code == 302
    user.refresh_from_db()
    assert not user.notifications_send
    assert latest_action_type(user) == 'eventyay.user.settings.notifications.disabled'


@pytest.mark.django_db
def test_turning_notifications_on_logs_enabled(client):
    user = User.objects.create_user(email='notif_on@example.com', password='password123')
    user.notifications_send = False
    user.save(update_fields=['notifications_send'])
    client.force_login(user)

    response = client.post(reverse('eventyay_common:account.notifications'), {'notifications_send': 'on'})

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.notifications_send
    assert latest_action_type(user) == 'eventyay.user.settings.notifications.enabled'
