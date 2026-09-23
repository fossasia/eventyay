import base64
from unittest import mock

import pytest
from django.urls import reverse
from django.utils import timezone

from eventyay.base.models import User, WebAuthnDevice
from eventyay.common.consts import KEY_LAST_FORCE_LOGIN


def login_recently(client, user):
    """These views require a recent authentication (RecentAuthenticationRequiredMixin)."""
    client.force_login(user)
    session = client.session
    session[KEY_LAST_FORCE_LOGIN] = timezone.now().timestamp()
    session.save()


def make_unconfirmed_device(client, user, *, with_session=True):
    device = WebAuthnDevice.objects.create(user=user, name='security key', confirmed=False)
    if with_session:
        session = client.session
        session['webauthn_challenge'] = base64.b64encode(b'challenge').decode()
        session['webauthn_register_ukey'] = base64.b64encode(b'ukey').decode()
        session.save()
    return device


def confirm_url(device):
    return reverse('eventyay_common:account.2fa.confirm.webauthn', kwargs={'device_id': device.pk})


@pytest.mark.django_db
@pytest.mark.parametrize(
    'payload,with_session',
    [
        ({'token': '{}'}, True),  # verification rejects the credential -> WebAuthnException
        ({'token': 'not json'}, True),  # json.loads -> ValueError
        ({}, True),  # request.POST.get('token') is None -> TypeError
        ({'token': '{}'}, False),  # missing challenge in session -> KeyError
    ],
)
def test_webauthn_registration_failure_keeps_the_device_unconfirmed(client, payload, with_session):
    user = User.objects.create_user(email='webauthn_fail@example.org', password='password123')
    login_recently(client, user)
    device = make_unconfirmed_device(client, user, with_session=with_session)

    response = client.post(confirm_url(device), payload)

    assert response.status_code == 302
    assert response['Location'] == confirm_url(device)
    device.refresh_from_db()
    assert not device.confirmed


@pytest.mark.django_db
def test_failure_after_the_device_is_saved_is_not_swallowed(client):
    """A post-save failure must not be funnelled into the confirmation redirect.

    That view only loads devices with confirmed=False, so redirecting there after the
    device has been confirmed told the user registration failed and then 404'd, even
    though the device was registered and usable.
    """
    user = User.objects.create_user(email='webauthn_postsave@example.org', password='password123')
    login_recently(client, user)
    device = make_unconfirmed_device(client, user)

    verification = mock.Mock(
        credential_id=b'credential-id',
        credential_public_key=b'public-key',
        sign_count=0,
    )

    with mock.patch('webauthn.verify_registration_response', return_value=verification):
        with mock.patch.object(User, 'send_security_notice', side_effect=RuntimeError('mail backend down')):
            with pytest.raises(RuntimeError):
                client.post(confirm_url(device), {'token': '{}'})

    device.refresh_from_db()
    assert device.confirmed


@pytest.mark.django_db
def test_credential_already_registered_is_rejected(client):
    """The duplicate check compares against the stored (encoded) credential id.

    Comparing the raw bytes never matched, so the same credential could be
    registered twice and the "already registered" message never appeared.
    """
    from eventyay.helpers.u2f import websafe_encode

    raw_credential_id = b'\x01\x02\x03duplicate-credential'

    owner = User.objects.create_user(email='webauthn_owner@example.org', password='password123')
    WebAuthnDevice.objects.create(
        user=owner,
        name='existing key',
        confirmed=True,
        credential_id=websafe_encode(raw_credential_id),
    )

    user = User.objects.create_user(email='webauthn_dupe@example.org', password='password123')
    login_recently(client, user)
    device = make_unconfirmed_device(client, user)

    verification = mock.Mock(
        credential_id=raw_credential_id,
        credential_public_key=b'public-key',
        sign_count=0,
    )
    with mock.patch('webauthn.verify_registration_response', return_value=verification):
        response = client.post(confirm_url(device), {'token': '{}'})

    assert response.status_code == 302
    assert response['Location'] == confirm_url(device)
    device.refresh_from_db()
    assert not device.confirmed
