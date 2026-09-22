import pytest
from django.urls import reverse
from django_otp.plugins.otp_static.models import StaticDevice

from eventyay.base.models import User
from eventyay.common.consts import KEY_LAST_FORCE_LOGIN
from django.utils import timezone


def login_recently(client, user):
    """These views require a recent authentication (RecentAuthenticationRequiredMixin)."""
    client.force_login(user)
    session = client.session
    session[KEY_LAST_FORCE_LOGIN] = timezone.now().timestamp()
    session.save()


@pytest.mark.django_db
def test_regenerating_emergency_codes_logs_a_displayable_action(client):
    user = User.objects.create_user(email='regen2fa@example.org', password='password123')
    login_recently(client, user)

    response = client.post(reverse('eventyay_common:account.2fa.regenemergency'))

    assert response.status_code == 302
    entry = user.all_logentries.order_by('-datetime', '-id').first()
    assert entry is not None
    assert entry.action_type == 'eventyay.user.settings.2fa.regenemergency'
    # display() falls back to the raw action_type when nothing renders it.
    assert entry.display() != entry.action_type
    assert str(entry.display()) == 'Your two-factor emergency codes have been regenerated.'


@pytest.mark.django_db
def test_regenerating_emergency_codes_replaces_the_tokens(client):
    user = User.objects.create_user(email='regen2fa_tokens@example.org', password='password123')
    login_recently(client, user)

    client.post(reverse('eventyay_common:account.2fa.regenemergency'))
    device = StaticDevice.objects.get(user=user, name='emergency')
    first = set(device.token_set.values_list('token', flat=True))
    assert len(first) == 10

    client.post(reverse('eventyay_common:account.2fa.regenemergency'))
    device = StaticDevice.objects.get(user=user, name='emergency')
    second = set(device.token_set.values_list('token', flat=True))
    assert len(second) == 10
    assert not (first & second)
