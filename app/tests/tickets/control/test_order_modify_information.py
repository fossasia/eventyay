import datetime
from decimal import Decimal

import pytest
from django.core import mail
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import RequestFactory, TestCase, override_settings
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import (
    Event,
    InvoiceAddress,
    LogEntry,
    Order,
    OrderPosition,
    Organizer,
    Product,
    Question,
    QuestionAnswer,
    Team,
    User,
)
from eventyay.base.views.mixins import OrderQuestionsViewMixin


rf = RequestFactory()


class MockView(OrderQuestionsViewMixin):
    def __init__(self, order, req):
        self.order = order
        self.request = req


@pytest.fixture
def modify_env():
    mail.outbox.clear()
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy Org', slug='dummy-org')
        event = Event.objects.create(
            organizer=organizer,
            name='Dummy Event',
            slug='dummy-event',
            date_from=now() + datetime.timedelta(days=30),
            plugins='eventyay.plugins.banktransfer',
            live=True,
            tickets_published=True,
        )
        event.settings.invoice_address_asked = True
        event.settings.invoice_address_required = True
        event.settings.attendee_names_asked = True
        event.settings.attendee_emails_asked = True
        event.settings.attendee_company_asked = True

        user = User.objects.create_user('admin@dummy.dummy', 'dummy')
        team = Team.objects.create(
            organizer=organizer,
            can_view_orders=True,
            can_change_orders=True,
        )
        team.members.add(user)
        team.limit_events.add(event)

    with scope(event=event, organizer=organizer):
        product = Product.objects.create(
            event=event,
            name='Ticket',
            default_price=Decimal('25.00'),
            admission=True,
        )

        q_choice = Question.objects.create(
            event=event,
            question='T-Shirt Size',
            type=Question.TYPE_CHOICE,
            required=True,
        )
        opt_s = q_choice.options.create(answer='S')
        opt_m = q_choice.options.create(answer='M')
        product.questions.add(q_choice)

        order = Order.objects.create(
            code='MOD1',
            event=event,
            email='customer@dummy.test',
            status=Order.STATUS_PAID,
            datetime=now() - datetime.timedelta(days=1),
            expires=now() + datetime.timedelta(days=10),
            total=Decimal('50.00'),
        )

        inv_addr = InvoiceAddress.objects.create(
            order=order,
            is_business=False,
            name_parts={'full_name': 'Original Invoicee', '_scheme': 'full'},
            street='Original Street 1',
            zipcode='12345',
            city='Original City',
            country='DE',
        )

        pos1 = OrderPosition.objects.create(
            order=order,
            positionid=1,
            product=product,
            price=Decimal('25.00'),
            attendee_name_parts={'full_name': 'Original Attendee 1', '_scheme': 'full'},
            attendee_email='att1@dummy.test',
            company='Original Company 1',
        )
        ans1 = QuestionAnswer.objects.create(
            orderposition=pos1,
            question=q_choice,
            answer='S',
        )
        ans1.options.add(opt_s)

        pos2 = OrderPosition.objects.create(
            order=order,
            positionid=2,
            product=product,
            price=Decimal('25.00'),
            attendee_name_parts={'full_name': 'Original Attendee 2', '_scheme': 'full'},
            attendee_email='att2@dummy.test',
            company='Original Company 2',
        )
        ans2 = QuestionAnswer.objects.create(
            orderposition=pos2,
            question=q_choice,
            answer='M',
        )
        ans2.options.add(opt_m)

    return {
        'organizer': organizer,
        'event': event,
        'user': user,
        'product': product,
        'question': q_choice,
        'opt_s': opt_s,
        'opt_m': opt_m,
        'order': order,
        'inv_addr': inv_addr,
        'pos1': pos1,
        'pos2': pos2,
    }


def _build_modify_data(env, **overrides):
    pos1 = env['pos1']
    pos2 = env['pos2']
    data = {
        'name_parts_0': 'New Invoicee',
        'street': 'New Street 42',
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f'{pos1.pk}-attendee_name_parts_0': 'Updated Attendee 1',
        f'{pos1.pk}-attendee_email': 'updated1@dummy.test',
        f'{pos1.pk}-company': 'Updated Company 1',
        f'{pos1.pk}-question_{env["question"].pk}': env['opt_m'].identifier,
        f'{pos2.pk}-attendee_name_parts_0': 'Updated Attendee 2',
        f'{pos2.pk}-attendee_email': 'updated2@dummy.test',
        f'{pos2.pk}-company': 'Updated Company 2',
        f'{pos2.pk}-question_{env["question"].pk}': env['opt_s'].identifier,
        'other-notify': 'on',
    }
    data.update(overrides)
    return data


def _build_initial_order_data(env, **overrides):
    pos1 = env['pos1']
    pos2 = env['pos2']
    data = {
        'name_parts_0': 'Original Invoicee',
        'street': 'Original Street 1',
        'zipcode': '12345',
        'city': 'Original City',
        'country': 'DE',
        f'{pos1.pk}-attendee_name_parts_0': 'Original Attendee 1',
        f'{pos1.pk}-attendee_email': 'att1@dummy.test',
        f'{pos1.pk}-company': 'Original Company 1',
        f'{pos1.pk}-question_{env["question"].pk}': env['opt_s'].identifier,
        f'{pos2.pk}-attendee_name_parts_0': 'Original Attendee 2',
        f'{pos2.pk}-attendee_email': 'att2@dummy.test',
        f'{pos2.pk}-company': 'Original Company 2',
        f'{pos2.pk}-question_{env["question"].pk}': env['opt_m'].identifier,
    }
    data.update(overrides)
    return data


def _setup_file_answer(env, question_text, filename, content=b'sample content'):
    with scope(event=env['event'], organizer=env['organizer']):
        q_file = Question.objects.create(
            event=env['event'],
            question=question_text,
            type=Question.TYPE_FILE,
            required=False,
        )
        env['product'].questions.add(q_file)
        test_file = SimpleUploadedFile(filename, content, content_type='application/pdf')
        ans = QuestionAnswer.objects.create(
            orderposition=env['pos1'],
            question=q_file,
            file=test_file,
        )
        return q_file, ans, ans.file.name, ans.pk


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_valid_submission_saves_all_changes(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f'/control/event/{env["organizer"].slug}/{env["event"].slug}/orders/{env["order"].code}/info'
    data = _build_modify_data(env)

    with TestCase.captureOnCommitCallbacks(execute=False) as callbacks:
        response = client.post(url, data, follow=False)
    assert response.status_code == 302
    assert response['Location'].endswith(f'/orders/{env["order"].code}/')

    # Notifications must NOT be sent before callbacks execute
    assert len(mail.outbox) == 0
    assert len(callbacks) > 0

    # Execute captured on_commit callbacks
    for cb in callbacks:
        cb()

    assert len(mail.outbox) == 1
    assert 'Your order has been changed' in mail.outbox[0].subject

    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'New Invoicee'
        assert env['inv_addr'].street == 'New Street 42'

        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Updated Attendee 1'
        assert env['pos1'].attendee_email == 'updated1@dummy.test'
        assert env['pos1'].company == 'Updated Company 1'
        assert env['pos1'].answers.get(question=env['question']).answer == 'M'

        env['pos2'].refresh_from_db()
        assert env['pos2'].attendee_name == 'Updated Attendee 2'
        assert env['pos2'].attendee_email == 'updated2@dummy.test'
        assert env['pos2'].company == 'Updated Company 2'
        assert env['pos2'].answers.get(question=env['question']).answer == 'S'

        assert LogEntry.objects.filter(
            content_type__model='order',
            object_id=env['order'].pk,
            action_type='eventyay.event.order.modified',
        ).exists()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_transaction_rollback_does_not_send_notification(client, modify_env, monkeypatch):
    """Proves that a rolled-back transaction discards on_commit callbacks and sends no notifications."""
    env = modify_env
    client.force_login(env['user'])

    url = f'/control/event/{env["organizer"].slug}/{env["event"].slug}/orders/{env["order"].code}/info'
    data = _build_modify_data(env)

    original_on_commit = transaction.on_commit

    def on_commit_fail(callback, using=None):
        original_on_commit(callback, using=using)
        raise RuntimeError('Simulated failure inside transaction after registering callback')

    monkeypatch.setattr(transaction, 'on_commit', on_commit_fail)

    with TestCase.captureOnCommitCallbacks(execute=True):
        with pytest.raises(RuntimeError, match='Simulated failure inside transaction'):
            client.post(url, data, follow=False)

    assert len(mail.outbox) == 0
    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'
        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Original Attendee 1'


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_simultaneous_attendee_and_invoice_errors_both_rendered(client, modify_env):
    """Verifies that all attendee, invoice, and auxiliary forms are validated,
    and multiple field errors from different forms are simultaneously presented in the response.
    """
    env = modify_env
    client.force_login(env['user'])

    url = f'/control/event/{env["organizer"].slug}/{env["event"].slug}/orders/{env["order"].code}/info'
    data = _build_modify_data(
        env,
        name_parts_0='Invalid Invoicee',
        street='Street',
        country='US',
        state='',  # Invalid invoice address (missing US state)
        **{
            f'{env["pos1"].pk}-attendee_email': 'invalid-email-pos1',
            f'{env["pos2"].pk}-attendee_email': 'invalid-email-pos2',
            f'{env["pos2"].pk}-question_{env["question"].pk}': '',  # Missing required question
        },
    )

    response = client.post(url, data, follow=False)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'We had difficulties processing your input' in content

    # Invoice error is present
    assert 'This field is required' in content
    # Attendee email errors are present
    assert 'Enter a valid email address' in content


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_invalid_invoice_form_preserves_all_attendee_and_order_info(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f'/control/event/{env["organizer"].slug}/{env["event"].slug}/orders/{env["order"].code}/info'
    data = _build_modify_data(env, country='INVALID')

    response = client.post(url, data, follow=False)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'We had difficulties processing your input' in content

    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'
        assert env['inv_addr'].street == 'Original Street 1'

        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Original Attendee 1'
        assert env['pos1'].attendee_email == 'att1@dummy.test'
        assert env['pos1'].company == 'Original Company 1'
        assert env['pos1'].answers.get(question=env['question']).answer == 'S'

        env['pos2'].refresh_from_db()
        assert env['pos2'].attendee_name == 'Original Attendee 2'
        assert env['pos2'].attendee_email == 'att2@dummy.test'
        assert env['pos2'].company == 'Original Company 2'
        assert env['pos2'].answers.get(question=env['question']).answer == 'M'

        assert not LogEntry.objects.filter(
            content_type__model='order',
            object_id=env['order'].pk,
            action_type='eventyay.event.order.modified',
        ).exists()

        assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_invalid_attendee_form_prevents_partial_changes(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f'/control/event/{env["organizer"].slug}/{env["event"].slug}/orders/{env["order"].code}/info'
    data = _build_modify_data(env, **{f'{env["pos1"].pk}-attendee_email': 'invalid-email'})

    response = client.post(url, data, follow=False)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'We had difficulties processing your input' in content

    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'
        assert env['inv_addr'].street == 'Original Street 1'

        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Original Attendee 1'
        assert env['pos1'].attendee_email == 'att1@dummy.test'
        assert env['pos1'].company == 'Original Company 1'
        assert env['pos1'].answers.get(question=env['question']).answer == 'S'

        env['pos2'].refresh_from_db()
        assert env['pos2'].attendee_name == 'Original Attendee 2'
        assert env['pos2'].attendee_email == 'att2@dummy.test'
        assert env['pos2'].company == 'Original Company 2'
        assert env['pos2'].answers.get(question=env['question']).answer == 'M'

        assert not LogEntry.objects.filter(
            content_type__model='order',
            object_id=env['order'].pk,
            action_type='eventyay.event.order.modified',
        ).exists()

        assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_presale_order_modify_invalid_invoice_leaves_attendee_info_unchanged(client, modify_env):
    env = modify_env
    client.force_login(env['user'])
    with scope(event=env['event'], organizer=env['organizer']):
        env['order'].email = env['user'].email
        env['order'].save()

    url = f'/{env["organizer"].slug}/{env["event"].slug}/order/{env["order"].code}/{env["order"].secret}/modify'

    data = {
        'name_parts_0': 'New Presale Invoicee',
        'street': '',  # invalid because invoice_address_required is True
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f'{env["pos1"].pk}-attendee_name_parts_0': 'Presale Attendee 1',
        f'{env["pos1"].pk}-attendee_email': 'presale1@dummy.test',
        f'{env["pos1"].pk}-company': 'Presale Company 1',
        f'{env["pos1"].pk}-question_{env["question"].pk}': env['opt_m'].identifier,
        f'{env["pos2"].pk}-attendee_name_parts_0': 'Presale Attendee 2',
        f'{env["pos2"].pk}-attendee_email': 'presale2@dummy.test',
        f'{env["pos2"].pk}-company': 'Presale Company 2',
        f'{env["pos2"].pk}-question_{env["question"].pk}': env['opt_s'].identifier,
    }

    response = client.post(url, data, follow=False)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'We had difficulties processing your input' in content
    assert 'This field is required' in content

    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'
        assert env['inv_addr'].street == 'Original Street 1'

        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Original Attendee 1'
        assert env['pos1'].attendee_email == 'att1@dummy.test'
        assert env['pos1'].company == 'Original Company 1'
        assert env['pos1'].answers.get(question=env['question']).answer == 'S'

        env['pos2'].refresh_from_db()
        assert env['pos2'].attendee_name == 'Original Attendee 2'
        assert env['pos2'].attendee_email == 'att2@dummy.test'
        assert env['pos2'].company == 'Original Company 2'
        assert env['pos2'].answers.get(question=env['question']).answer == 'M'

        assert not LogEntry.objects.filter(
            content_type__model='order',
            object_id=env['order'].pk,
            action_type='eventyay.event.order.modified',
        ).exists()


@pytest.mark.django_db
def test_duplicate_answer_recovery_inside_transaction(modify_env):
    """Verifies that duplicate-key IntegrityError inside an atomic transaction recovers via savepoint."""
    env = modify_env
    with scope(event=env['event'], organizer=env['organizer']):
        new_q = Question.objects.create(
            event=env['event'],
            question='Dietary Requirement',
            type=Question.TYPE_STRING,
            required=False,
        )
        env['product'].questions.add(new_q)

    request = rf.post(
        '/',
        data=_build_initial_order_data(
            env,
            **{f'{env["pos1"].pk}-question_{new_q.pk}': 'Vegetarian'},
        ),
    )
    request.event = env['event']

    view = MockView(env['order'], request)
    # Instantiate forms while pos1 does not yet have an answer for new_q in memory
    _ = view.forms

    # Simulate race condition: another request created the answer before view.save() runs
    with scope(event=env['event'], organizer=env['organizer']):
        QuestionAnswer.objects.create(
            orderposition=env['pos1'],
            question=new_q,
            answer='Old Answer',
        )

    # Calling save() inside an atomic transaction must recover without TransactionManagementError
    with transaction.atomic():
        success = view.save()

    assert success is True
    with scope(event=env['event'], organizer=env['organizer']):
        ans = QuestionAnswer.objects.get(orderposition=env['pos1'], question=new_q)
        assert ans.answer == 'Vegetarian'


@pytest.mark.django_db
def test_file_answer_deferred_deletion_on_commit_and_rollback(modify_env):
    """Verifies that clearing an uploaded file defers deletion until transaction commit,
    and retains the file in storage if the transaction rolls back.
    """
    env = modify_env
    q_file, ans, file_path, ans_pk = _setup_file_answer(env, 'Passport Scan', 'passport.pdf')
    assert default_storage.exists(file_path)

    # Case 1: Rollback retains the existing file
    req_clear = rf.post(
        '/',
        data=_build_initial_order_data(
            env,
            **{f'{env["pos1"].pk}-question_{q_file.pk}-clear': 'on'},
        ),
    )
    req_clear.event = env['event']
    view1 = MockView(env['order'], req_clear)
    _ = view1.forms

    try:
        with transaction.atomic():
            view1.save()
            raise RuntimeError('Simulated failure after save')
    except RuntimeError:
        view1.cleanup_staged_uploads()

    # The file in storage must NOT have been deleted
    assert default_storage.exists(file_path)
    with scope(event=env['event'], organizer=env['organizer']):
        reloaded_ans = QuestionAnswer.objects.get(pk=ans_pk)
        assert reloaded_ans.file.name == file_path

    # Case 2: Commit deletes the file after on_commit callbacks run
    req_clear_commit = rf.post(
        '/',
        data=_build_initial_order_data(
            env,
            **{f'{env["pos1"].pk}-question_{q_file.pk}-clear': 'on'},
        ),
    )
    req_clear_commit.event = env['event']
    view2 = MockView(env['order'], req_clear_commit)
    _ = view2.forms

    with TestCase.captureOnCommitCallbacks(execute=True):
        with transaction.atomic():
            success = view2.save()
            assert success is True

    # After commit, file is deleted from storage and QA record is gone
    assert not default_storage.exists(file_path)
    with scope(event=env['event'], organizer=env['organizer']):
        assert not QuestionAnswer.objects.filter(pk=ans_pk).exists()


@pytest.mark.django_db
def test_file_answer_replacement_and_staged_cleanup_on_rollback(modify_env):
    """Verifies that replacing an uploaded file deletes staged uploads on rollback
    while preserving the original file, and completes deletion of old file on commit.
    """
    env = modify_env
    q_file, ans, old_file_path, ans_pk = _setup_file_answer(env, 'Student ID', 'id_old.pdf', b'old content')
    assert default_storage.exists(old_file_path)

    # Case 1: Replacement in rolled-back transaction cleans up staged upload and preserves old file
    new_uploaded_file1 = SimpleUploadedFile('id_new1.pdf', b'new content 1', content_type='application/pdf')
    req_replace_fail = rf.post(
        '/',
        data=_build_initial_order_data(
            env,
            **{f'{env["pos1"].pk}-question_{q_file.pk}': new_uploaded_file1},
        ),
    )
    req_replace_fail.event = env['event']
    view1 = MockView(env['order'], req_replace_fail)
    _ = view1.forms

    staged_path = None
    try:
        with transaction.atomic():
            view1.save()
            # Staged file was written during save()
            assert len(view1._staged_uploads) == 1
            _, staged_path = view1._staged_uploads[0]
            assert default_storage.exists(staged_path)
            raise RuntimeError('Abort after upload')
    except RuntimeError:
        view1.cleanup_staged_uploads()

    # Staged file was deleted on cleanup, old file is still retained
    assert not default_storage.exists(staged_path)
    assert default_storage.exists(old_file_path)
    with scope(event=env['event'], organizer=env['organizer']):
        reloaded = QuestionAnswer.objects.get(pk=ans_pk)
        assert reloaded.file.name == old_file_path

    # Case 2: Replacement in committed transaction removes old file and retains new file
    new_uploaded_file2 = SimpleUploadedFile('id_new2.pdf', b'new content 2', content_type='application/pdf')
    req_replace_commit = rf.post(
        '/',
        data=_build_initial_order_data(
            env,
            **{f'{env["pos1"].pk}-question_{q_file.pk}': new_uploaded_file2},
        ),
    )
    req_replace_commit.event = env['event']
    view2 = MockView(env['order'], req_replace_commit)
    _ = view2.forms

    with TestCase.captureOnCommitCallbacks(execute=True):
        with transaction.atomic():
            success = view2.save()
            assert success is True

    assert not default_storage.exists(old_file_path)
    with scope(event=env['event'], organizer=env['organizer']):
        reloaded = QuestionAnswer.objects.get(pk=ans_pk)
        new_file_path = reloaded.file.name
        assert default_storage.exists(new_file_path)
        # Clean up created file from test storage
        default_storage.delete(new_file_path)
