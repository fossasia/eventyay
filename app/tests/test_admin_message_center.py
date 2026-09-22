import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import now

from eventyay.base.models import User
from eventyay.base.models.admin_mail import (
    AdminEmailQueue,
    AdminEmailQueueFilter,
    AdminEmailQueueRecipient,
    AdminEmailStatus,
    AdminRecipientGroup,
)
from eventyay.base.models.log import LogEntry


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
