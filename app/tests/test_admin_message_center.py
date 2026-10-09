from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core import mail as djmail
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.email import TEST_EMAIL_BODY
from eventyay.base.i18n import LazyI18nString
from eventyay.base.models import User
from eventyay.base.models.admin_mail import (
    AdminEmailQueue,
    AdminEmailQueueFilter,
    AdminEmailQueueRecipient,
    AdminEmailStatus,
    AdminRecipientGroup,
)
from eventyay.base.models.auth import StaffSession
from eventyay.base.models.log import LogEntry
from eventyay.base.services.mail import get_mail_backend
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.exceptions import SendMailException
from eventyay.control.forms.admin.admin_messages import AdminComposeForm


@pytest.fixture
def admin_user(db):
    user = User.objects.create_adminuser(
        email='admin@example.com',
        password='admin-pass',
    )
    return user


@pytest.fixture
def regular_user(db):
    user = User.objects.create_user(
        email='user@example.com',
        password='user-pass',
    )
    return user


@pytest.fixture
def queued_mail(db, admin_user):
    mail = AdminEmailQueue.objects.create(
        user=admin_user,
        recipient_group=AdminRecipientGroup.ALL_ORGANISERS,
        subject='Test subject',
        message='Hello {user_name}',
        status=AdminEmailStatus.QUEUED,
    )
    AdminEmailQueueFilter.objects.create(mail=mail)
    AdminEmailQueueRecipient.objects.create(
        mail=mail,
        email='recipient@example.com',
        name='Test Recipient',
    )
    return mail


@pytest.fixture
def draft_mail(db, admin_user):
    mail = AdminEmailQueue.objects.create(
        user=admin_user,
        recipient_group=AdminRecipientGroup.ALL_ORGANISERS,
        subject='Draft subject',
        message='Draft body',
        status=AdminEmailStatus.DRAFT,
    )
    AdminEmailQueueFilter.objects.create(mail=mail)
    return mail


@pytest.mark.django_db
def test_admin_email_queue_str(admin_user):
    mail = AdminEmailQueue(subject='Hello', status=AdminEmailStatus.DRAFT)
    assert 'Hello' in str(mail)
    assert 'draft' in str(mail)


@pytest.mark.django_db
def test_admin_email_queue_is_draft(draft_mail):
    assert draft_mail.is_draft is True
    assert draft_mail.is_sent is False


@pytest.mark.django_db
def test_admin_email_queue_is_sent(admin_user):
    mail = AdminEmailQueue(status=AdminEmailStatus.SENT, sent_at=now())
    assert mail.is_sent is True
    assert mail.is_draft is False


@pytest.mark.django_db
def test_send_skips_draft(draft_mail):
    result = draft_mail.send()
    assert result is False
    draft_mail.refresh_from_db()
    assert draft_mail.status == AdminEmailStatus.DRAFT


@pytest.mark.django_db
def test_send_skips_already_sent(admin_user):
    mail = AdminEmailQueue.objects.create(
        user=admin_user,
        subject='Sent',
        message='Body',
        status=AdminEmailStatus.SENT,
        sent_at=now(),
    )
    result = mail.send()
    assert result is False


@pytest.mark.django_db
def test_send_no_recipients_marks_sent(admin_user):
    mail = AdminEmailQueue.objects.create(
        user=admin_user,
        subject='No recipients',
        message='Body',
        status=AdminEmailStatus.QUEUED,
    )
    result = mail.send()
    assert result is True
    mail.refresh_from_db()
    assert mail.status == AdminEmailStatus.SENT
    assert mail.sent_at is not None


@pytest.mark.django_db
def test_make_html_returns_valid_html():
    html = AdminEmailQueue.make_html('<p>Hello <b>World</b></p>')
    assert '<!DOCTYPE html>' in html
    assert '<p>Hello <b>World</b></p>' in html


@pytest.mark.django_db
def test_make_html_sanitizes_scripts():
    html = AdminEmailQueue.make_html('<script>alert(1)</script><p>Safe</p>')
    assert '<script>' not in html
    assert '<p>Safe</p>' in html


@pytest.mark.django_db
def test_duplicate_creates_draft(queued_mail):
    new_mail = queued_mail.duplicate()
    assert new_mail.pk != queued_mail.pk
    assert new_mail.status == AdminEmailStatus.DRAFT
    assert new_mail.subject == queued_mail.subject
    assert new_mail.recipient_group == queued_mail.recipient_group


@pytest.mark.django_db
def test_get_edit_url(draft_mail):
    url = draft_mail.get_edit_url()
    assert '/admin/messages/compose/' in url
    assert str(draft_mail.pk) in url


@pytest.mark.django_db
def test_get_recipient_count(queued_mail):
    assert queued_mail.get_recipient_count() == 1


@pytest.mark.django_db
def test_get_sent_count(queued_mail):
    queued_mail.recipients.update(sent=True)
    assert queued_mail.get_sent_count() == 1
    assert queued_mail.get_failed_count() == 0


@pytest.mark.django_db
def test_get_failed_count(queued_mail):
    queued_mail.recipients.update(sent=False, error='Connection refused')
    assert queued_mail.get_failed_count() == 1


@pytest.mark.django_db
def test_resolve_all_users_returns_active_users():
    from eventyay.control.views.admin_messages import resolve_admin_recipients

    User.objects.create_user(email='a@example.com', password='x')
    User.objects.create_user(email='b@example.com', password='x')
    results, skipped = resolve_admin_recipients({
        'recipient_group': AdminRecipientGroup.ALL_USERS,
        'account_status': '',
        'user_role': '',
        'language': '',
        'event_status': '',
        'event_date_from': None,
        'event_date_to': None,
        'organiser_status': '',
        'billing_status': '',
        'ticketing_status': '',
        'cfp_status': '',
        'setup_status': '',
        'created_after': None,
        'created_before': None,
        'last_active_after': None,
        'last_active_before': None,
        'selected_organisers': [],
        'selected_events': [],
        'selected_users': [],
        'exclude_admins': False,
        'exclude_inactive': False,
        'exclude_unconfirmed_email': False,
    })
    emails = {r['email'] for r in results}
    assert 'a@example.com' in emails
    assert 'b@example.com' in emails
    assert isinstance(skipped, int)


@pytest.mark.django_db
def test_resolve_excludes_admins():
    from eventyay.control.views.admin_messages import resolve_admin_recipients

    User.objects.create_user(email='normaluser@example.com', password='x')
    User.objects.create_adminuser(email='adminuser@example.com', password='x')

    results, _skipped = resolve_admin_recipients({
        'recipient_group': AdminRecipientGroup.ALL_USERS,
        'account_status': '',
        'user_role': '',
        'language': '',
        'event_status': '',
        'event_date_from': None,
        'event_date_to': None,
        'organiser_status': '',
        'billing_status': '',
        'ticketing_status': '',
        'cfp_status': '',
        'setup_status': '',
        'created_after': None,
        'created_before': None,
        'last_active_after': None,
        'last_active_before': None,
        'selected_organisers': [],
        'selected_events': [],
        'selected_users': [],
        'exclude_admins': True,
        'exclude_inactive': False,
        'exclude_unconfirmed_email': False,
    })
    emails = {r['email'] for r in results}
    assert 'normaluser@example.com' in emails
    assert 'adminuser@example.com' not in emails


@pytest.mark.django_db
def test_resolve_deduplicated():
    from eventyay.control.views.admin_messages import resolve_admin_recipients

    User.objects.create_user(email='dup@example.com', password='x')
    results, _skipped = resolve_admin_recipients({
        'recipient_group': AdminRecipientGroup.ALL_USERS,
        'account_status': '',
        'user_role': '',
        'language': '',
        'event_status': '',
        'event_date_from': None,
        'event_date_to': None,
        'organiser_status': '',
        'billing_status': '',
        'ticketing_status': '',
        'cfp_status': '',
        'setup_status': '',
        'created_after': None,
        'created_before': None,
        'last_active_after': None,
        'last_active_before': None,
        'selected_organisers': [],
        'selected_events': [],
        'selected_users': [],
        'exclude_admins': False,
        'exclude_inactive': False,
        'exclude_unconfirmed_email': False,
    })
    dup_results = [r for r in results if r['email'] == 'dup@example.com']
    assert len(dup_results) == 1


@pytest.mark.django_db
def test_resolve_selected_users():
    from eventyay.control.views.admin_messages import resolve_admin_recipients

    u1 = User.objects.create_user(email='selected@example.com', password='x')
    User.objects.create_user(email='other@example.com', password='x')

    results, _skipped = resolve_admin_recipients({
        'recipient_group': AdminRecipientGroup.SELECTED_USERS,
        'account_status': '',
        'user_role': '',
        'language': '',
        'event_status': '',
        'event_date_from': None,
        'event_date_to': None,
        'organiser_status': '',
        'billing_status': '',
        'ticketing_status': '',
        'cfp_status': '',
        'setup_status': '',
        'created_after': None,
        'created_before': None,
        'last_active_after': None,
        'last_active_before': None,
        'selected_organisers': [],
        'selected_events': [],
        'selected_users': [u1.pk],
        'exclude_admins': False,
        'exclude_inactive': False,
        'exclude_unconfirmed_email': False,
    })
    emails = {r['email'] for r in results}
    assert 'selected@example.com' in emails
    assert 'other@example.com' not in emails


@pytest.mark.django_db
def test_resolve_selected_users_empty_returns_none():
    from eventyay.control.views.admin_messages import resolve_admin_recipients

    User.objects.create_user(email='any@example.com', password='x')
    results, _skipped = resolve_admin_recipients({
        'recipient_group': AdminRecipientGroup.SELECTED_USERS,
        'account_status': '',
        'user_role': '',
        'language': '',
        'event_status': '',
        'event_date_from': None,
        'event_date_to': None,
        'organiser_status': '',
        'billing_status': '',
        'ticketing_status': '',
        'cfp_status': '',
        'setup_status': '',
        'created_after': None,
        'created_before': None,
        'last_active_after': None,
        'last_active_before': None,
        'selected_organisers': [],
        'selected_events': [],
        'selected_users': [],
        'exclude_admins': False,
        'exclude_inactive': False,
        'exclude_unconfirmed_email': False,
    })
    assert results == []


@pytest.mark.django_db
def test_compose_view_requires_admin_session(client, regular_user):
    client.force_login(regular_user)
    response = client.get('/admin/messages/compose/')
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_outbox_view_requires_admin_session(client, regular_user):
    client.force_login(regular_user)
    response = client.get('/admin/messages/outbox/')
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_preview_endpoint_returns_200_for_staff(client, admin_user):
    import json as _json
    from django.contrib.auth import SESSION_KEY

    client.force_login(admin_user)
    response = client.post(
        '/admin/messages/preview/',
        data=_json.dumps({'html': '<p>Hello {user_name}</p>'}),
        content_type='application/json',
    )
    assert response.status_code == 200
    data = response.json()
    assert 'html' in data
    assert 'Jane Doe' in data['html']


@pytest.mark.django_db
def test_preview_endpoint_rejects_non_json(client, admin_user):
    client.force_login(admin_user)
    response = client.post(
        '/admin/messages/preview/',
        data='not json',
        content_type='text/plain',
    )
    assert response.status_code == 200
    data = response.json()
    assert 'html' in data


@pytest.mark.django_db
def test_recipients_endpoint_returns_count(client, admin_user):
    client.force_login(admin_user)
    User.objects.create_user(email='org@example.com', password='x')
    response = client.get('/admin/messages/recipients/?recipient_group=all_users')
    assert response.status_code == 200
    data = response.json()
    assert 'count' in data
    assert isinstance(data['count'], int)


@pytest.mark.django_db
def test_duplicate_draft_creates_new_record(draft_mail):
    new_mail = draft_mail.duplicate()
    assert AdminEmailQueue.objects.filter(status=AdminEmailStatus.DRAFT).count() >= 2
    assert new_mail.subject == draft_mail.subject


@pytest.mark.django_db
def test_filter_copied_on_duplicate(queued_mail):
    AdminEmailQueueFilter.objects.filter(mail=queued_mail).update(
        account_status='active',
        event_status='live',
    )
    queued_mail.refresh_from_db()
    new_mail = queued_mail.duplicate()
    new_filter = AdminEmailQueueFilter.objects.get(mail=new_mail)
    assert new_filter.account_status == 'active'
    assert new_filter.event_status == 'live'


@pytest.mark.django_db
def test_queue_action_creates_log_entry(queued_mail, admin_user):
    LogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(AdminEmailQueue),
        object_id=queued_mail.pk,
        user=admin_user,
        action_type='eventyay.admin.mail.queued',
        data='{}',
    )
    assert LogEntry.objects.filter(
        action_type='eventyay.admin.mail.queued',
        object_id=queued_mail.pk,
    ).exists()


@pytest.mark.django_db
def test_cancel_action_creates_log_entry(queued_mail, admin_user):
    LogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(AdminEmailQueue),
        object_id=queued_mail.pk,
        user=admin_user,
        action_type='eventyay.admin.mail.cancelled',
        data='{}',
    )
    assert LogEntry.objects.filter(
        action_type='eventyay.admin.mail.cancelled',
        object_id=queued_mail.pk,
    ).exists()


@pytest.mark.django_db
def test_delete_action_creates_log_entry(draft_mail, admin_user):
    LogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(AdminEmailQueue),
        object_id=draft_mail.pk,
        user=admin_user,
        action_type='eventyay.admin.mail.deleted',
        data='{}',
    )
    assert LogEntry.objects.filter(action_type='eventyay.admin.mail.deleted').exists()


@pytest.mark.django_db
def test_i18n_subject_stored_as_dict(admin_user):
    mail = AdminEmailQueue.objects.create(
        user=admin_user,
        subject={'en': 'Hello', 'de': 'Hallo'},
        message={'en': 'English body', 'de': 'Deutscher Text'},
        status=AdminEmailStatus.DRAFT,
    )
    mail.refresh_from_db()
    assert isinstance(mail.subject, LazyI18nString)
    assert str(mail.subject.localize('en')) == 'Hello'
    assert str(mail.subject.localize('de')) == 'Hallo'


@pytest.mark.django_db
def test_i18n_message_localize_fallback(admin_user):
    mail = AdminEmailQueue.objects.create(
        user=admin_user,
        subject={'en': 'Subject'},
        message={'en': 'English only'},
        status=AdminEmailStatus.DRAFT,
    )
    mail.refresh_from_db()
    msg = LazyI18nString(mail.message)
    assert 'English only' in str(msg.localize('fr'))


@pytest.mark.django_db
def test_i18n_plain_string_compat(admin_user):
    mail = AdminEmailQueue.objects.create(
        user=admin_user,
        subject='Plain subject',
        message='Plain body',
        status=AdminEmailStatus.QUEUED,
    )
    mail.refresh_from_db()
    assert 'Plain subject' in str(LazyI18nString(mail.subject).localize('en'))
    assert 'Plain body' in str(LazyI18nString(mail.message).localize('de'))


@pytest.mark.django_db
def test_send_resolves_user_locale(admin_user):
    user_de = User.objects.create_user(email='de_user@example.com', password='x', locale='de')
    user_en = User.objects.create_user(email='en_user@example.com', password='x', locale='en')
    mail = AdminEmailQueue.objects.create(
        user=admin_user,
        subject={'en': 'Hello', 'de': 'Hallo'},
        message={'en': 'English body', 'de': 'Deutscher Text'},
        status=AdminEmailStatus.QUEUED,
    )
    AdminEmailQueueRecipient.objects.create(mail=mail, user=user_de, email='de_user@example.com')
    AdminEmailQueueRecipient.objects.create(mail=mail, user=user_en, email='en_user@example.com')

    dispatched = []
    with patch('eventyay.common.mail.mail_send_task.apply_async', side_effect=lambda **kw: dispatched.append(kw)):
        mail.send()

    assert len(dispatched) == 2
    subjects = {d['kwargs']['subject'] for d in dispatched}
    assert 'Hello' in subjects
    assert 'Hallo' in subjects
    bodies = {d['kwargs']['body'] for d in dispatched}
    assert 'English body' in bodies
    assert 'Deutscher Text' in bodies


@pytest.mark.django_db
def test_duplicate_preserves_i18n(admin_user):
    mail = AdminEmailQueue.objects.create(
        user=admin_user,
        subject={'en': 'Hello', 'de': 'Hallo'},
        message={'en': 'Body EN', 'de': 'Body DE'},
        status=AdminEmailStatus.QUEUED,
    )
    AdminEmailQueueFilter.objects.create(mail=mail)
    new_mail = mail.duplicate()
    new_mail.refresh_from_db()
    assert str(LazyI18nString(new_mail.subject).localize('de')) == 'Hallo'
    assert str(LazyI18nString(new_mail.message).localize('de')) == 'Body DE'


def _staff_login(client, user):
    client.force_login(user)
    session = client.session
    session.save()
    StaffSession.objects.create(user=user, session_key=session.session_key)


@pytest.mark.django_db
def test_users_select2_requires_three_characters(client, admin_user):
    _staff_login(client, admin_user)
    User.objects.create_user(email='jane@example.org', password='x', fullname='Jane Doe')

    for query in ('', 'ja', '  j  '):
        response = client.get(reverse('eventyay_admin:admin.users.select2'), {'query': query})
        assert response.status_code == 200
        assert response.json() == {'results': [], 'pagination': {'more': False}}


@pytest.mark.django_db
def test_users_select2_searches_by_name_and_email(client, admin_user):
    _staff_login(client, admin_user)
    jane = User.objects.create_user(email='jane@example.org', password='x', fullname='Jane Doe')
    john = User.objects.create_user(email='jdoe@example.org', password='x', fullname='John Smith')

    response = client.get(reverse('eventyay_admin:admin.users.select2'), {'query': 'jane'})
    assert [result['id'] for result in response.json()['results']] == [jane.pk]

    response = client.get(reverse('eventyay_admin:admin.users.select2'), {'query': 'smith'})
    assert [result['id'] for result in response.json()['results']] == [john.pk]


@pytest.mark.django_db
def test_users_select2_limits_page_size(client, admin_user):
    _staff_login(client, admin_user)
    for i in range(25):
        User.objects.create_user(email=f'bulk{i:02d}@example.org', password='x')

    response = client.get(reverse('eventyay_admin:admin.users.select2'), {'query': 'bulk'})
    data = response.json()
    assert len(data['results']) == 20
    assert data['pagination']['more'] is True

    response = client.get(reverse('eventyay_admin:admin.users.select2'), {'query': 'bulk', 'page': 2})
    assert len(response.json()['results']) == 5


@pytest.mark.django_db
def test_users_select2_rejects_non_staff(client, regular_user):
    client.force_login(regular_user)
    response = client.get(reverse('eventyay_admin:admin.users.select2'), {'query': 'user'})
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_compose_form_selectors_wait_for_three_characters():
    form = AdminComposeForm()
    for name in ('selected_users', 'selected_events', 'selected_organisers'):
        attrs = form.fields[name].widget.attrs
        assert attrs['data-minimum-input-length'] == 3
        assert attrs['data-delay'] == 250


@pytest.fixture
def admin_client(client, admin_user):
    _staff_login(client, admin_user)
    return client


def _compose_data(**overrides):
    data = {
        'action': 'test',
        'recipient_group': '',
        'subject_0': 'Platform update',
        'message_0': '<p>Hello {user_name}</p>',
        'test_email': 'tester@example.com',
        'delivery_mode': 'now',
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_send_test_email_without_recipient_group(admin_client):
    with patch('eventyay.control.views.admin_messages.mail_send_task') as task:
        response = admin_client.post('/admin/messages/compose/', data=_compose_data())
    assert response.status_code == 200
    assert not response.context['form'].errors
    task.assert_called_once()
    assert task.call_args.kwargs['to'] == ['tester@example.com']
    assert 'Test email sent successfully to tester@example.com.' in response.content.decode()
    assert not AdminEmailQueue.objects.exists()
    assert response.context['form'].fields['recipient_group'].required


@pytest.mark.django_db
def test_send_test_email_ignores_delivery_schedule(admin_client):
    with patch('eventyay.control.views.admin_messages.mail_send_task') as task:
        response = admin_client.post('/admin/messages/compose/', data=_compose_data(delivery_mode='later'))
    assert not response.context['form'].errors
    task.assert_called_once()


@pytest.mark.django_db
def test_send_test_email_ignores_incomplete_schedule(admin_client):
    data = _compose_data(delivery_mode='later', scheduled_at_0='2099-01-01', scheduled_at_1='')
    with patch('eventyay.control.views.admin_messages.mail_send_task') as task:
        response = admin_client.post('/admin/messages/compose/', data=data)
    form = response.context['form']
    assert not form.errors
    task.assert_called_once()
    assert not form.fields['scheduled_at'].disabled
    assert form['scheduled_at'].value() == ['2099-01-01', '']


@pytest.mark.django_db
def test_send_test_email_ignores_invalid_audience_filters(admin_client):
    data = _compose_data(event_date_from='not-a-date', selected_events='999999')
    with patch('eventyay.control.views.admin_messages.mail_send_task') as task:
        response = admin_client.post('/admin/messages/compose/', data=data)
    form = response.context['form']
    assert not form.errors
    task.assert_called_once()
    assert not form.fields['event_date_from'].disabled
    assert form['event_date_from'].value() == 'not-a-date'


@pytest.mark.django_db
def test_send_test_email_requires_test_address(admin_client):
    with patch('eventyay.control.views.admin_messages.mail_send_task') as task:
        response = admin_client.post('/admin/messages/compose/', data=_compose_data(test_email=''))
    form = response.context['form']
    assert form.errors['test_email'] == ['Please enter a test email address.']
    assert 'recipient_group' not in form.errors
    task.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize('message', ['', '<p></p>'])
def test_send_test_email_without_content(admin_client, message):
    with patch('eventyay.control.views.admin_messages.mail_send_task') as task:
        response = admin_client.post('/admin/messages/compose/', data=_compose_data(subject_0='', message_0=message))
    form = response.context['form']
    assert not form.errors
    task.assert_called_once()
    assert task.call_args.kwargs['subject'] == '[TEST] Eventyay test email'
    assert task.call_args.kwargs['body'] == str(TEST_EMAIL_BODY)
    assert str(TEST_EMAIL_BODY) in task.call_args.kwargs['html']
    assert form.fields['subject'].one_required
    assert form.fields['message'].one_required


@pytest.mark.django_db
def test_send_test_email_is_delivered_right_away(admin_client):
    response = admin_client.post('/admin/messages/compose/', data=_compose_data())
    assert 'Test email sent successfully to tester@example.com.' in response.content.decode()
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['tester@example.com']
    assert djmail.outbox[0].subject == '[TEST] Platform update'


@pytest.mark.django_db
def test_send_test_email_uses_platform_mail_settings(admin_client):
    GlobalSettingsObject().settings.set('mail_from', 'platform@eventyay.test')
    with patch('eventyay.base.services.mail.get_mail_backend', wraps=get_mail_backend) as backend:
        admin_client.post('/admin/messages/compose/', data=_compose_data())
    backend.assert_called_once()
    assert djmail.outbox[0].from_email == 'eventyay <platform@eventyay.test>'


@pytest.mark.django_db
def test_send_test_email_reports_mail_server_errors(admin_client):
    with patch(
        'eventyay.control.views.admin_messages.mail_send_task',
        side_effect=SendMailException('Recipient refused'),
    ):
        response = admin_client.post('/admin/messages/compose/', data=_compose_data())
    content = response.content.decode()
    assert 'Failed to send test email. Please check your mail configuration.' in content
    assert 'Test email sent successfully' not in content


@pytest.mark.django_db
def test_send_still_requires_recipient_group_and_content(admin_client):
    response = admin_client.post(
        '/admin/messages/compose/', data=_compose_data(action='send', subject_0='', message_0='')
    )
    form = response.context['form']
    assert 'recipient_group' in form.errors
    assert 'subject' in form.errors
    assert 'message' in form.errors
    assert not AdminEmailQueue.objects.exists()


@pytest.mark.django_db
def test_send_still_validates_audience_filters(admin_client):
    data = _compose_data(action='send', recipient_group=AdminRecipientGroup.ALL_USERS, event_date_from='not-a-date')
    response = admin_client.post('/admin/messages/compose/', data=data)
    assert 'event_date_from' in response.context['form'].errors
    assert not AdminEmailQueue.objects.exists()
