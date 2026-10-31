import json
import re
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from eventyay.base.forms.organizer_request import OrganizerRequestForm
from eventyay.base.models import (
    Organizer,
    OrganizerRequest,
    OrganizerRequestAnswer,
    OrganizerRequestFieldSetting,
    OrganizerRequestQuestion,
    User,
)
from eventyay.base.models.auth import StaffSession
from eventyay.base.organizer_request_fields import organizer_request_enabled
from eventyay.base.services.organizer_requests import review_request
from eventyay.eventyay_common.views.organizer_request import OrganizerRequestCreate


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def disable_video_cache_updates():
    with patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync'):
        yield


@pytest.fixture
def data():
    return {
        'name': 'Jane Example',
        'email': 'Jane@example.com',
        'affiliation': 'Example community',
        'events': 'A local meetup',
        'organizer_name': 'Example',
        'slug': 'example-community',
    }


@pytest.fixture
def application(data):
    return OrganizerRequest.objects.create(**{**data, 'email': data['email'].lower()})


@pytest.fixture
def admin(client):
    user = User.objects.create_user('admin@example.com', 'secret', is_staff=True)
    client.force_login(user)
    StaffSession.objects.create(user=user, session_key=client.session.session_key)
    return user


def test_public_form_and_submission(client, data, django_capture_on_commit_callbacks):
    User.objects.create_user('admin@example.com', is_staff=True)
    User.objects.create_user('super@example.com', is_superuser=True)
    page = client.get('/invite')
    assert page.status_code == 200
    html = page.content.decode()
    assert 'form-horizontal' in html
    assert html.count('required-indicator') == 6
    assert 'organizer-request-grid' not in html
    assert 'How you will use Eventyay' not in html
    assert 'We will sell tickets' not in html
    with (
        patch('eventyay.base.services.organizer_requests.mail') as mail,
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = client.post('/invite', data)
    assert response.status_code == 302
    assert response.url == reverse('organizer_request.success')
    assert 'within a few business days' in client.get(response.url).content.decode()
    assert OrganizerRequest.objects.get().email == 'jane@example.com'
    assert {call.args[0] for call in mail.call_args_list} == {
        'jane@example.com',
        'admin@example.com',
        'super@example.com',
    }
    assert not User.objects.filter(email='jane@example.com').exists()


def test_same_form_when_logged_in(client, admin):
    assert client.get('/invite').status_code == 200


@pytest.mark.parametrize('slug', ['UPPER', 'two words', 'control', 'invite', '-bad', 'bad/', 'a' * 51])
def test_invalid_slugs(client, data, slug):
    assert not OrganizerRequestForm(data={**data, 'slug': slug}).is_valid()
    assert client.get(reverse('organizer_request.slug'), {'slug': slug}).json()['available'] is False


def test_taken_slug(client, data):
    Organizer.objects.create(name='Existing', slug=data['slug'].upper())
    assert not OrganizerRequestForm(data=data).is_valid()
    assert not client.get(reverse('organizer_request.slug'), {'slug': data['slug']}).json()['available']
    assert client.get(reverse('organizer_request.slug'), {'slug': 'available'}).json()['available']


def test_duplicate_pending_email(application, data):
    assert 'email' in OrganizerRequestForm(data=data).errors
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizerRequest.objects.create(**data)
    application.status = 'rejected'
    application.save()
    assert OrganizerRequestForm(data=data).is_valid()


def test_honeypot(data):
    assert not OrganizerRequestForm(data={**data, 'website': 'spam'}).is_valid()


def test_rate_limit(client, settings):
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    settings.TRUST_X_FORWARDED_FOR = True
    cache.clear()
    for _ in range(10):
        assert (
            client.post('/invite', {}, REMOTE_ADDR='198.51.100.1', HTTP_X_FORWARDED_FOR='192.0.2.1').status_code == 200
        )
    response = client.post('/invite', {}, REMOTE_ADDR='198.51.100.1', HTTP_X_FORWARDED_FOR='192.0.2.1')
    assert response.status_code == 429
    assert response['Retry-After'] == '900'
    assert client.post('/invite', {}, REMOTE_ADDR='198.51.100.1', HTTP_X_FORWARDED_FOR='192.0.2.2').status_code == 200
    cache.clear()


def test_slug_endpoint_rate_limit_and_max_length(client, monkeypatch, settings):
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    settings.TRUST_X_FORWARDED_FOR = True
    cache.clear()
    long_slug = client.get(reverse('organizer_request.slug'), {'slug': 'a' * 51})
    assert long_slug.status_code == 200
    assert long_slug.json()['available'] is False
    assert '50' in long_slug.json()['message']
    monkeypatch.setattr('eventyay.eventyay_common.views.organizer_request.ORGANIZER_REQUEST_SLUG_RATE_LIMIT', 1)
    assert (
        client.get(
            reverse('organizer_request.slug'), {'slug': 'available'}, HTTP_X_FORWARDED_FOR='192.0.2.1'
        ).status_code
        == 200
    )
    response = client.get(reverse('organizer_request.slug'), {'slug': 'available'}, HTTP_X_FORWARDED_FOR='192.0.2.1')
    assert response.status_code == 429
    assert response['Retry-After'] == '900'
    assert (
        client.get(
            reverse('organizer_request.slug'), {'slug': 'available'}, HTTP_X_FORWARDED_FOR='192.0.2.2'
        ).status_code
        == 200
    )
    cache.clear()


def test_organizer_request_form_loads_settings_once():
    with CaptureQueriesContext(connection) as queries:
        OrganizerRequestForm()
    query_sql = [query['sql'].lower() for query in queries.captured_queries]
    assert sum('base_organizerrequestfieldsetting' in sql for sql in query_sql) == 1
    assert sum('base_organizerrequestquestion' in sql for sql in query_sql) == 1


def test_approve_new_account(application, admin, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        result = review_request(application.pk, admin, approve=True, organizer_name='Edited name', slug='edited')
    assert result.status == 'approved'
    assert result.reviewed_by == admin and result.reviewed_at
    assert result.organizer.name == 'Edited name'
    assert result.new_account
    assert result.user.fullname == application.name
    assert not result.user.has_usable_password()
    team = result.user.teams.get(organizer=result.organizer)
    assert team.name == 'Core Organizing Team'
    assert team.can_create_events and team.all_events and team.can_change_teams
    assert len(mailoutbox) == 1
    assert f'We have created an Eventyay account with {application.email}.' in mailoutbox[0].body
    assert 'Set your password and access your organiser:' in mailoutbox[0].body
    assert reverse('eventyay_common:auth.forgot.recover') + '?id=' in mailoutbox[0].body
    with pytest.raises(ValidationError):
        review_request(application.pk, admin, approve=True, organizer_name='Again', slug='again')
    assert not Organizer.objects.filter(slug='again').exists()


def test_existing_account(application, admin, mailoutbox, django_capture_on_commit_callbacks):
    user = User.objects.create_user(application.email, 'existing-password')
    with django_capture_on_commit_callbacks(execute=True):
        result = review_request(application.pk, admin, approve=True, organizer_name='Example', slug='example')
    assert len(mailoutbox) == 1
    assert 'organiser has been added to your existing Eventyay account' in mailoutbox[0].body
    assert 'sign in with your existing Eventyay account' in mailoutbox[0].body
    assert 'You do not need to create a new account or set a new password.' in mailoutbox[0].body
    assert result.user == user and not result.new_account
    user.refresh_from_db()
    assert user.check_password('existing-password')
    assert user.teams.filter(organizer=result.organizer, can_create_events=True).exists()


def test_reject(application, admin, django_capture_on_commit_callbacks):
    with (
        patch('eventyay.base.services.organizer_requests.mail') as mail,
        django_capture_on_commit_callbacks(execute=True),
    ):
        result = review_request(application.pk, admin, approve=False, reason='Please tell us more')
    assert result.status == 'rejected' and result.reviewed_by == admin
    assert not User.objects.filter(email=application.email).exists()
    assert result.organizer is None
    assert 'Please tell us more' in mail.call_args.args[3]['body']


def test_admin_review_pages(client, application, admin):
    url = reverse('eventyay_admin:admin.organizer_requests.detail', args=[application.pk])
    assert client.get(reverse('eventyay_admin:admin.organizer_requests')).status_code == 200
    assert client.get(url).status_code == 200
    response = client.post(url, {'action': 'approve', 'organizer_name': 'Changed', 'slug': 'changed'})
    assert response.status_code == 302
    application.refresh_from_db()
    assert application.status == 'approved'
    assert client.get(url).status_code == 200


def test_non_admin_cannot_review(client, application):
    client.force_login(User.objects.create_user('other@example.com'))
    url = reverse('eventyay_admin:admin.organizer_requests.detail', args=[application.pk])
    assert client.get(url).status_code == 403
    assert client.post(url, {'action': 'reject'}).status_code == 403
    application.refresh_from_db()
    assert application.status == 'pending'


def test_password_setup_and_reuse(client, application, admin):
    result = review_request(application.pk, admin, approve=True, organizer_name='Example', slug='example')
    client.logout()
    token = default_token_generator.make_token(result.user)
    url = reverse('eventyay_common:auth.forgot.recover') + f'?id={result.user.pk}&token={token}'
    assert client.get(url).status_code == 200
    before_login = int(time.time())
    response = client.post(
        url, {'password': 'Correct-Horse-Battery-123!', 'password_repeat': 'Correct-Horse-Battery-123!'}
    )
    assert response.status_code == 302
    assert response.url == reverse('control:organizer', kwargs={'organizer': 'example'})
    assert str(client.session['_auth_user_id']) == str(result.user.pk)
    assert before_login <= client.session['eventyay_auth_login_time'] <= int(time.time())
    client.logout()
    assert client.get(url).url == reverse('eventyay_common:auth.forgot')


def test_expired_setup_link(client, application, admin, settings):
    result = review_request(application.pk, admin, approve=True, organizer_name='Example', slug='example')
    token = default_token_generator.make_token(result.user)
    client.logout()
    settings.PASSWORD_RESET_TIMEOUT = -1
    url = reverse('eventyay_common:auth.forgot.recover') + f'?id={result.user.pk}&token={token}'
    assert client.get(url).url == reverse('eventyay_common:auth.forgot')
    result.user.refresh_from_db()
    assert not result.user.has_usable_password()


def test_reject_with_taken_slug(client, application, admin):
    Organizer.objects.create(name='Taken', slug=application.slug)
    url = reverse('eventyay_admin:admin.organizer_requests.detail', args=[application.pk])
    assert client.post(url, {'action': 'reject', 'reason': ''}).status_code == 302
    application.refresh_from_db()
    assert application.status == 'rejected'


def test_slug_collision_rolls_back(application, admin):
    Organizer.objects.create(name='Taken', slug='taken')
    with pytest.raises(ValidationError):
        review_request(application.pk, admin, approve=True, organizer_name='Example', slug='taken')
    assert not User.objects.filter(email=application.email).exists()
    application.refresh_from_db()
    assert application.status == 'pending'


@pytest.mark.parametrize('flag', ['is_spam', 'is_active'])
def test_disabled_accounts_not_granted_access(application, admin, flag):
    User.objects.create_user(application.email, **{flag: flag == 'is_spam'})
    with pytest.raises(ValidationError):
        review_request(application.pk, admin, approve=True, organizer_name='Example', slug='example')
    assert not Organizer.objects.filter(slug='example').exists()


def test_events_length(data):
    assert 'events' in OrganizerRequestForm(data={**data, 'events': 'x' * 10001}).errors


def test_normal_password_reset_does_not_auto_login(client):
    user = User.objects.create_user('existing@example.com', 'old-password')
    token = default_token_generator.make_token(user)
    url = reverse('eventyay_common:auth.forgot.recover') + f'?id={user.pk}&token={token}'
    page = client.get(url).content.decode()
    assert 'Set new password' in page
    assert 'Set password and continue' not in page
    response = client.post(
        url, {'password': 'Correct-Horse-Battery-123!', 'password_repeat': 'Correct-Horse-Battery-123!'}
    )
    assert response.url == reverse('auth.login')
    assert '_auth_user_id' not in client.session


def test_forgot_password_replacement_link(client, application, admin, mailoutbox):
    result = review_request(application.pk, admin, approve=True, organizer_name='Example', slug='example')
    client.logout()
    response = client.post(reverse('eventyay_common:auth.forgot'), {'email': application.email})
    assert response.status_code == 302
    assert len(mailoutbox) == 1
    assert f'id={result.user.pk}' in mailoutbox[0].body
    assert 'token=' in mailoutbox[0].body


def test_submission_email_rendering(client, data, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post('/invite', data).status_code == 302
    assert len(mailoutbox) == 1
    assert 'within a few business days' in mailoutbox[0].body


def test_welcome_email_password_link(client, application, admin, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        result = review_request(application.pk, admin, approve=True, organizer_name='Example', slug='example')
    assert len(mailoutbox) == 1
    body = mailoutbox[0].body
    assert 'Set your password' in body
    assert 'signed in and taken to your organiser dashboard' in body
    assert application.email in body
    setup_url = re.search(r'https?://[^\s]+/forgot/recover/\?[^\s)]+', body).group()
    query = parse_qs(urlsplit(setup_url).query)
    assert query['id'] == [str(result.user.pk)]
    assert default_token_generator.check_token(result.user, query['token'][0])
    assert '&amp;' not in setup_url
    client.logout()
    page = client.get(setup_url)
    assert page.status_code == 200
    assert 'Welcome to Eventyay' in page.content.decode()
    assert 'Set password and continue' in page.content.decode()
    assert 'Example' in page.content.decode()
    assert 'create your first event' in page.content.decode()
    response = client.post(
        setup_url,
        {'password': 'Correct-Horse-Battery-123!', 'password_repeat': 'Correct-Horse-Battery-123!'},
    )
    assert response.url == reverse('control:organizer', kwargs={'organizer': result.organizer.slug})
    assert str(client.session['_auth_user_id']) == str(result.user.pk)


def test_onboarding_requires_two_factor_authentication(client, application, admin, settings):
    settings.OTP_TOTP_THROTTLE_FACTOR = 0
    result = review_request(application.pk, admin, approve=True, organizer_name='Example', slug='example')
    user = result.user
    user.require_2fa = True
    user.save(update_fields=['require_2fa'])
    device = TOTPDevice.objects.create(user=user, name='test')
    client.logout()
    token = default_token_generator.make_token(user)
    url = reverse('eventyay_common:auth.forgot.recover') + f'?id={user.pk}&token={token}'
    response = client.post(
        url, {'password': 'Correct-Horse-Battery-123!', 'password_repeat': 'Correct-Horse-Battery-123!'}
    )
    destination = reverse('control:organizer', kwargs={'organizer': 'example'})
    assert urlsplit(response.url).path == reverse('auth.login.2fa')
    assert parse_qs(urlsplit(response.url).query)['next'] == [destination]
    assert '_auth_user_id' not in client.session
    assert 'eventyay_auth_login_time' not in client.session
    assert client.session['eventyay_auth_2fa_user'] == user.pk
    twofa_url = response.url
    retry = client.post(twofa_url, {'token': 'invalid'})
    assert parse_qs(urlsplit(retry.url).query)['next'] == [destination]
    assert '_auth_user_id' not in client.session
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    totp.time = time.time()
    response = client.post(retry.url, {'token': str(totp.token())})
    assert response.url == destination
    assert str(client.session['_auth_user_id']) == str(user.pk)
    assert client.session['eventyay_auth_login_time'] > 0
    assert 'eventyay_auth_2fa_user' not in client.session


@pytest.mark.parametrize('event_slug', ['success', 'slug'])
def test_invite_event_routes_are_preserved(event_slug):
    match = resolve(f'/invite/{event_slug}/')
    assert match.kwargs['organizer'] == 'invite'
    assert match.kwargs['event'] == event_slug
    assert not match.url_name.startswith('organizer_request.')


def test_approval_uses_queued_delivery(application, admin, django_capture_on_commit_callbacks):
    with (
        patch('eventyay.base.services.organizer_requests.mail') as mail,
        django_capture_on_commit_callbacks(execute=True),
    ):
        review_request(application.pk, admin, approve=True, organizer_name='Example', slug='example')
    assert mail.call_count == 1
    assert not mail.call_args.kwargs.get('sync_send', False)


def test_invite_organizer_index_route_is_preserved():
    match = resolve('/invite/')
    assert match.kwargs['organizer'] == 'invite'
    assert match.url_name == 'invite.organizer'
    assert resolve('/invite').url_name == 'organizer_request.create'


def test_pending_slug_reserved(client, application, data, admin):
    form = OrganizerRequestForm(data={**data, 'email': 'another@example.com'})
    assert 'slug' in form.errors
    assert not client.get(reverse('organizer_request.slug'), {'slug': application.slug}).json()['available']
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizerRequest.objects.create(**{**data, 'email': 'another@example.com', 'slug': application.slug.upper()})
    result = review_request(
        application.pk, admin, approve=True, organizer_name=application.organizer_name, slug=application.slug
    )
    assert result.status == 'approved'


def test_slug_race_returns_field_error(data, rf):
    form = OrganizerRequestForm(data=data)
    assert form.is_valid()
    OrganizerRequest.objects.create(**{**data, 'email': 'other@example.com'})
    view = OrganizerRequestCreate()
    view.setup(rf.post('/invite', data))
    response = view.form_valid(form)
    assert response.status_code == 200
    assert 'slug' in response.context_data['form'].errors


def test_staff_notification_excludes_applicant_text(client, data, admin, django_capture_on_commit_callbacks):
    with (
        patch('eventyay.base.services.organizer_requests.mail') as mail,
        django_capture_on_commit_callbacks(execute=True),
    ):
        client.post('/invite', {**data, 'events': '[Click me](https://untrusted.example)'})
    staff_mail = next(call for call in mail.call_args_list if call.args[0] == admin.email)
    body = staff_mail.args[3]['body']
    assert 'untrusted.example' not in body
    assert data['name'] not in body
    assert '/admin/organizer-requests/' in body


def test_required_question_is_stored_with_the_request(client, data):
    question = OrganizerRequestQuestion.objects.create(
        label='City', help_text='Where do you host events?', variant='string', required=True, position=20
    )
    page = client.get('/invite').content.decode()
    assert 'City' in page
    assert 'How you will use Eventyay' not in page
    assert client.post('/invite', data).status_code == 200
    response = client.post('/invite', {**data, f'question_{question.pk}': 'Berlin'})
    assert response.status_code == 302
    answer = OrganizerRequestAnswer.objects.get(question=question)
    assert answer.answer == 'Berlin'
    assert answer.request.email == 'jane@example.com'


def test_inactive_question_is_hidden(client):
    OrganizerRequestQuestion.objects.create(label='Secret budget', active=False, position=30)
    assert 'Secret budget' not in client.get('/invite').content.decode()


def test_admin_manages_organiser_form_questions(client, admin):
    list_url = reverse('eventyay_admin:admin.organizer_forms')
    page = client.get(list_url)
    assert page.status_code == 200
    assert 'Organiser forms' in page.content.decode()
    response = client.post(
        reverse('eventyay_admin:admin.organizer_forms.add'),
        {
            'label': 'Budget',
            'help_text': 'A rough yearly budget.',
            'variant': 'string',
            'required': 'on',
            'active': 'on',
        },
    )
    assert response.status_code == 302
    question = OrganizerRequestQuestion.objects.get(label='Budget')
    assert question.required is True
    response = client.post(
        reverse('eventyay_admin:admin.organizer_forms.edit', args=[question.pk]),
        {'label': 'Yearly budget', 'help_text': '', 'variant': 'string', 'active': 'on'},
    )
    assert response.status_code == 302
    question.refresh_from_db()
    assert question.label == 'Yearly budget'
    assert question.required is False


def test_admin_can_disable_public_organizer_requests(client, admin):
    list_url = reverse('eventyay_admin:admin.organizer_forms')
    page = client.get(list_url)
    assert 'Enable public organiser requests' in page.content.decode()
    assert 'id="organizer-request-enabled"' in page.content.decode()
    assert 'Confirm' in page.content.decode()
    response = client.post(reverse('eventyay_admin:admin.organizer_forms.request.toggle'))
    assert response.status_code == 302
    assert not organizer_request_enabled()
    page = client.get(list_url).content.decode()
    assert 'organiser-form-order' not in page
    assert 'New custom field' not in page
    assert client.get('/invite').status_code == 404
    assert client.get(reverse('organizer_request.success')).status_code == 404
    assert client.get(reverse('organizer_request.slug'), {'slug': 'available'}).status_code == 404
    assert client.post(reverse('organizer_request.slug')).status_code == 404
    response = client.post(reverse('eventyay_admin:admin.organizer_forms.request.toggle'), {'enabled': 'on'})
    assert response.status_code == 302
    assert organizer_request_enabled()
    assert client.get('/invite').status_code == 200


def test_default_fields_follow_active_required_and_position(client, admin, data):
    page = client.get(reverse('eventyay_admin:admin.organizer_forms')).content.decode()
    assert 'Your name' in page
    assert 'Events you organise' in page
    assert 'We will sell tickets' not in page
    affiliation = OrganizerRequestFieldSetting.objects.get(key='affiliation')
    response = client.post(
        reverse('eventyay_admin:admin.organizer_forms.field', args=['affiliation']),
        data=json.dumps({'field': 'required', 'value': 'optional'}),
        content_type='application/json',
    )
    assert response.status_code == 200
    affiliation.refresh_from_db()
    assert affiliation.required is False
    response = client.post(
        reverse('eventyay_admin:admin.organizer_forms.field', args=['email']),
        data=json.dumps({'field': 'active', 'value': False}),
        content_type='application/json',
    )
    assert response.status_code == 400
    events = OrganizerRequestFieldSetting.objects.get(key='events')
    events.active = False
    events.save(update_fields=['active'])
    html = client.get('/invite').content.decode()
    assert 'Events you organise' not in html
    payload = {key: value for key, value in data.items() if key != 'events'}
    assert client.post('/invite', payload).status_code == 302
    stored = OrganizerRequest.objects.get(email='jane@example.com')
    assert stored.events == ''
    order = 'field:name,field:email,field:organizer_name,field:slug,field:events,field:affiliation'
    assert client.post(reverse('eventyay_admin:admin.organizer_forms.order'), {'order': order}).status_code == 302
    events.refresh_from_db()
    assert events.position == 4
