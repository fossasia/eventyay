import datetime
from decimal import Decimal

import pytest
from django.core import mail
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
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


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_valid_submission_saves_all_changes(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    data = {
        'name_parts_0': 'New Invoicee',
        'street': 'New Street 42',
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'updated1@dummy.test',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'updated2@dummy.test',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

    with TestCase.captureOnCommitCallbacks(execute=False) as callbacks:
        response = client.post(url, data, follow=False)
    assert response.status_code == 302
    assert response['Location'].endswith(f"/orders/{env['order'].code}/")

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
def test_transaction_rollback_does_not_send_notification(client, modify_env):
    """Proves that a rolled-back transaction registers no callbacks and sends no notifications."""
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    data = {
        'name_parts_0': 'Invalid Invoicee',
        'street': 'Street',
        'zipcode': '12345',
        'city': 'City',
        'country': 'US',
        'state': '',  # invalid
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'updated1@dummy.test',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'updated2@dummy.test',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

    with TestCase.captureOnCommitCallbacks(execute=False) as callbacks:
        response = client.post(url, data, follow=False)
    assert response.status_code == 200
    assert len(callbacks) == 0
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_simultaneous_attendee_and_invoice_errors_both_rendered(client, modify_env):
    """Verifies that all attendee, invoice, and auxiliary forms are validated,
    and multiple field errors from different forms are simultaneously presented in the response.
    """
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    data = {
        'name_parts_0': 'Invalid Invoicee',
        'street': 'Street',
        'zipcode': '12345',
        'city': 'City',
        'country': 'US',
        'state': '',  # Invalid invoice address (missing US state)
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'invalid-email-pos1',  # Invalid pos1 email
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'invalid-email-pos2',  # Invalid pos2 email
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": '',  # Missing required question choice
        'other-notify': 'on',
    }

    response = client.post(url, data, follow=False)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'We had difficulties processing your input' in content

    # Invoice error is present
    assert 'This field is required' in content
    # Attendee email errors are present
    assert 'Enter a valid email address' in content


@pytest.mark.django_db
def test_concurrent_modifications_do_not_overwrite_unrelated_fields(modify_env):
    """Verifies that race conditions arising from interleaved or stale submissions (where
    two forms are constructed concurrently from the same initial database state before either is saved)
    refresh order positions and invoice addresses inside the transaction and apply only changed_data,
    ensuring unrelated edits do not overwrite each other.

    Note: True multi-threaded/multi-connection concurrency testing (e.g. holding an uncommitted lock
    in thread A while thread B attempts to acquire it) requires pytest-django transactional database
    teardown (`transaction=True`), which triggers `django-admin flush` on teardown and fails in this
    test suite due to legacy schema table foreign-key constraints. Hence, this test verifies
    the stale-submission and in-transaction refresh/selective-update semantics deterministically.
    """
    env = modify_env
    factory = RequestFactory()

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

    with scope(event=env['event'], organizer=env['organizer']):
        order_pk = env['order'].pk
        pos1_pk = env['pos1'].pk
        pos2_pk = env['pos2'].pk
        inv_pk = env['inv_addr'].pk
        q_pk = env['question'].pk
        opt_s_id = env['opt_s'].identifier
        opt_m_id = env['opt_m'].identifier

        # Both User A and User B concurrently load the order modification form from the DB.
        # User A updates pos1 attendee_name and invoice street.
        req_a = factory.post(
            '/',
            data={
                'name_parts_0': 'Original Invoicee',
                'street': 'User A Street',
                'zipcode': '12345',
                'city': 'Original City',
                'country': 'DE',
                f'{pos1_pk}-attendee_name_parts_0': 'User A New Name',
                f'{pos1_pk}-attendee_email': 'att1@dummy.test',
                f'{pos1_pk}-company': 'Original Company 1',
                f'{pos1_pk}-question_{q_pk}': opt_s_id,
                f'{pos2_pk}-attendee_name_parts_0': 'Original Attendee 2',
                f'{pos2_pk}-attendee_email': 'att2@dummy.test',
                f'{pos2_pk}-company': 'Original Company 2',
                f'{pos2_pk}-question_{q_pk}': opt_m_id,
            },
        )
        req_a.event = env['event']
        view_a = MockView(Order.objects.get(pk=order_pk), req_a)
        assert view_a.is_valid()
        assert view_a.invoice_form.is_valid()

        # User B concurrently loaded the form (so initial pos1 attendee_name is 'Original Attendee 1'
        # and invoice street is 'Original Street 1').
        # User B modifies pos1 company, pos2 attendee_name, and invoice city.
        # User B leaves pos1 attendee_name and invoice street unchanged.
        req_b = factory.post(
            '/',
            data={
                'name_parts_0': 'Original Invoicee',
                'street': 'Original Street 1',  # stale data from initial load
                'zipcode': '12345',
                'city': 'User B City',          # updated
                'country': 'DE',
                f'{pos1_pk}-attendee_name_parts_0': 'Original Attendee 1',  # stale
                f'{pos1_pk}-attendee_email': 'att1@dummy.test',
                f'{pos1_pk}-company': 'User B Company',                     # updated
                f'{pos1_pk}-question_{q_pk}': opt_s_id,
                f'{pos2_pk}-attendee_name_parts_0': 'User B Attendee 2',    # updated
                f'{pos2_pk}-attendee_email': 'att2@dummy.test',
                f'{pos2_pk}-company': 'Original Company 2',
                f'{pos2_pk}-question_{q_pk}': opt_m_id,
            },
        )
        req_b.event = env['event']
        view_b = MockView(Order.objects.get(pk=order_pk), req_b)
        assert view_b.is_valid()
        assert view_b.invoice_form.is_valid()

        # User A saves first inside a transaction with order locking
        with transaction.atomic():
            env['event'].orders.select_for_update().filter(pk=order_pk).first()
            assert view_a.save() is True
            view_a.save_invoice_form()

        # User B saves second inside a transaction with order locking
        with transaction.atomic():
            env['event'].orders.select_for_update().filter(pk=order_pk).first()
            assert view_b.save() is True
            view_b.save_invoice_form()

        pos1 = OrderPosition.objects.get(pk=pos1_pk)
        pos2 = OrderPosition.objects.get(pk=pos2_pk)
        inv = InvoiceAddress.objects.get(pk=inv_pk)
        # Attendee fields from User A were preserved, and User B's were applied
        assert pos1.attendee_name == 'User A New Name'
        assert pos1.company == 'User B Company'
        assert pos2.attendee_name == 'User B Attendee 2'
        # Invoice fields from User A were preserved, and User B's were applied
        assert inv.street == 'User A Street'
        assert inv.city == 'User B City'


@pytest.mark.django_db
def test_stale_invoice_form_does_not_overwrite_concurrent_invoice_changes(modify_env):
    """Verifies that an invoice form submitted with stale initial data does not overwrite
    newer invoice fields modified concurrently.
    """
    env = modify_env
    factory = RequestFactory()

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

    with scope(event=env['event'], organizer=env['organizer']):
        # User A changes street to 'Street A'
        req_a = factory.post(
            '/',
            data={
                'name_parts_0': 'Original Invoicee',
                'street': 'Street A',
                'zipcode': '12345',
                'city': 'Original City',
                'country': 'DE',
            },
        )
        req_a.event = env['event']
        view_a = MockView(Order.objects.get(pk=env['order'].pk), req_a)
        assert view_a.invoice_form.is_valid()

        # User B concurrently loaded the form before A saved, and changes only city to 'City B'
        req_b = factory.post(
            '/',
            data={
                'name_parts_0': 'Original Invoicee',
                'street': 'Original Street 1',  # stale
                'zipcode': '12345',
                'city': 'City B',               # modified
                'country': 'DE',
            },
        )
        req_b.event = env['event']
        view_b = MockView(Order.objects.get(pk=env['order'].pk), req_b)
        assert view_b.invoice_form.is_valid()

        # A saves first inside transaction with locking
        with transaction.atomic():
            env['event'].orders.select_for_update().filter(pk=env['order'].pk).first()
            view_a.save_invoice_form()

        # B saves second inside transaction with locking
        with transaction.atomic():
            env['event'].orders.select_for_update().filter(pk=env['order'].pk).first()
            view_b.save_invoice_form()

        env['inv_addr'].refresh_from_db()
        # Street from A is preserved, city from B is applied
        assert env['inv_addr'].street == 'Street A'
        assert env['inv_addr'].city == 'City B'


@pytest.mark.django_db
def test_unmodified_invoice_form_does_not_overwrite_concurrent_invoice_changes(modify_env):
    """Verifies that when a submission modifies attendee positions but leaves the invoice form
    unmodified, save_invoice_form() does not overwrite concurrent invoice updates.
    """
    env = modify_env
    factory = RequestFactory()

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

    with scope(event=env['event'], organizer=env['organizer']):
        # Form B loaded while DB has original invoice values
        req_b = factory.post(
            '/',
            data={
                'name_parts_0': 'Original Invoicee',
                'street': 'Original Street 1',  # matches original initial data
                'zipcode': '12345',
                'city': 'Original City',
                'country': 'DE',
                f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Name Only',
                f"{env['pos1'].pk}-attendee_email": 'att1@dummy.test',
                f"{env['pos1'].pk}-company": 'Original Company 1',
                f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
                f"{env['pos2'].pk}-attendee_name_parts_0": 'Original Attendee 2',
                f"{env['pos2'].pk}-attendee_email": 'att2@dummy.test',
                f"{env['pos2'].pk}-company": 'Original Company 2',
                f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
            },
        )
        req_b.event = env['event']
        view_b = MockView(Order.objects.get(pk=env['order'].pk), req_b)
        assert view_b.is_valid()
        assert view_b.invoice_form.is_valid()
        assert not view_b.invoice_form.has_changed()

        # Concurrent process updates invoice address street
        InvoiceAddress.objects.filter(pk=env['inv_addr'].pk).update(street='Concurrent Street Update')

        # View B saves inside transaction with locking
        with transaction.atomic():
            env['event'].orders.select_for_update().filter(pk=env['order'].pk).first()
            assert view_b.save() is True
            view_b.save_invoice_form()

        env['inv_addr'].refresh_from_db()
        env['pos1'].refresh_from_db()
        # Attendee was updated
        assert env['pos1'].attendee_name == 'Updated Name Only'
        # Invoice address was NOT reverted to 'Original Street 1'
        assert env['inv_addr'].street == 'Concurrent Street Update'


@pytest.mark.django_db
def test_concurrent_creation_of_missing_invoice_address(modify_env):
    """Verifies that when an order initially has no invoice address and two submissions
    are loaded concurrently before any invoice address exists, Request A creates the
    invoice address and Request B recovers by updating the newly created invoice address
    without raising IntegrityError or creating duplicate records.
    """
    env = modify_env
    factory = RequestFactory()

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

    with scope(event=env['event'], organizer=env['organizer']):
        # Delete the fixture's invoice address so the order initially has NO invoice address
        env['inv_addr'].delete()
        order_pk = env['order'].pk
        order_a = Order.objects.get(pk=order_pk)
        order_b = Order.objects.get(pk=order_pk)
        assert InvoiceAddress.objects.filter(order_id=order_pk).count() == 0

        # Request A and Request B both load the modification form while no invoice address exists
        req_a = factory.post(
            '/',
            data={
                'name_parts_0': 'User A Name',
                'street': 'Street A',
                'zipcode': '11111',
                'city': 'City A',
                'country': 'DE',
            },
        )
        req_a.event = env['event']
        view_a = MockView(order_a, req_a)
        assert view_a.invoice_form.is_valid()
        assert view_a.invoice_form.instance.pk is None

        req_b = factory.post(
            '/',
            data={
                'name_parts_0': 'User B Name',
                'street': 'Street B',
                'zipcode': '22222',
                'city': 'City B',
                'country': 'DE',
            },
        )
        req_b.event = env['event']
        view_b = MockView(order_b, req_b)
        assert view_b.invoice_form.is_valid()
        assert view_b.invoice_form.instance.pk is None

        # Request A acquires lock and creates the invoice address inside transaction
        with transaction.atomic():
            env['event'].orders.select_for_update().filter(pk=order_pk).first()
            view_a.save_invoice_form()

        created_addr = InvoiceAddress.objects.get(order_id=order_pk)
        assert created_addr.street == 'Street A'
        assert created_addr.city == 'City A'
        assert created_addr.name == 'User A Name'

        # Request B arrives second; its form was built before the address existed (instance.pk is None).
        # Request B acquires lock and saves invoice form inside transaction.
        with transaction.atomic():
            env['event'].orders.select_for_update().filter(pk=order_pk).first()
            view_b.save_invoice_form()

        # Exactly ONE invoice address must exist for this order
        assert InvoiceAddress.objects.filter(order_id=order_pk).count() == 1
        created_addr.refresh_from_db()
        # Request B's changed fields were applied without IntegrityError
        assert created_addr.street == 'Street B'
        assert created_addr.city == 'City B'
        assert created_addr.name == 'User B Name'


@pytest.mark.django_db
def test_concurrent_creation_fallback_on_integrity_error(modify_env, monkeypatch):
    """Verifies that if an unexpected race condition causes an initial query check to miss
    a concurrent creation, save_invoice_form handles the IntegrityError inside a savepoint,
    re-queries the existing record, and updates it cleanly without failing the transaction.
    """
    env = modify_env
    factory = RequestFactory()

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].delete()
        order_pk = env['order'].pk
        order = Order.objects.get(pk=order_pk)

        req = factory.post(
            '/',
            data={
                'name_parts_0': 'Fallback Name',
                'street': 'Fallback Street',
                'zipcode': '33333',
                'city': 'Fallback City',
                'country': 'DE',
            },
        )
        req.event = env['event']
        view = MockView(order, req)
        assert view.invoice_form.is_valid()

        # Simulate race where existing check returns None, but another transaction committed an address
        orig_filter = InvoiceAddress.objects.filter
        first_call = True

        def simulated_filter(**kwargs):
            nonlocal first_call
            if first_call and kwargs.get('order') == order:
                first_call = False
                # Return empty queryset on the first check to simulate missing it
                return InvoiceAddress.objects.none()
            return orig_filter(**kwargs)

        # Before saving, create an existing record in the DB to cause IntegrityError on insert
        InvoiceAddress.objects.create(
            order=order,
            street='Race Pre-existing Street',
            city='Race City',
            country='DE',
        )

        monkeypatch.setattr(InvoiceAddress.objects, 'filter', simulated_filter)

        with transaction.atomic():
            view.save_invoice_form()

        assert InvoiceAddress.objects.filter(order=order).count() == 1
        addr = InvoiceAddress.objects.get(order=order)
        assert addr.street == 'Fallback Street'
        assert addr.city == 'Fallback City'
        assert addr.name == 'Fallback Name'


@pytest.mark.django_db
def test_save_invoice_form_propagates_unrelated_integrity_error(modify_env, monkeypatch):
    """Verifies that an unrelated IntegrityError (e.g. check constraint or foreign key violation)
    is not swallowed and is re-raised.
    """
    env = modify_env
    factory = RequestFactory()

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].delete()
        order_pk = env['order'].pk
        order = Order.objects.get(pk=order_pk)

        req = factory.post(
            '/',
            data={
                'name_parts_0': 'Some Name',
                'street': 'Some Street',
                'zipcode': '12345',
                'city': 'Some City',
                'country': 'DE',
            },
        )
        req.event = env['event']
        view = MockView(order, req)
        assert view.invoice_form.is_valid()

        # Case 1: Unrelated message without diag
        def fail_save_null(*args, **kwargs):
            raise IntegrityError("null value in column 'country' violates not-null constraint")

        monkeypatch.setattr(view.invoice_form, 'save', fail_save_null)

        with pytest.raises(IntegrityError, match="not-null constraint"):
            with transaction.atomic():
                view.save_invoice_form()

        # Case 2: PostgreSQL diagnostic with an unrelated constraint name
        class FakeDiag:
            constraint_name = 'base_organizer_slug_key'

        class FakeCause(Exception):
            diag = FakeDiag()

        def fail_save_unrelated_pg(*args, **kwargs):
            exc = IntegrityError("duplicate key value violates unique constraint 'base_organizer_slug_key'")
            exc.__cause__ = FakeCause()
            raise exc

        monkeypatch.setattr(view.invoice_form, 'save', fail_save_unrelated_pg)

        with pytest.raises(IntegrityError, match="base_organizer_slug_key"):
            with transaction.atomic():
                view.save_invoice_form()


@pytest.mark.django_db
def test_is_invoice_order_unique_violation_diagnostics():
    """Verifies exact constraint name matching on PostgreSQL, exact table.column matching
    on SQLite, and rejection of unrelated or unknown diagnostics.
    """
    class FakeDiag:
        def __init__(self, name):
            self.constraint_name = name

    class FakeCause(Exception):
        def __init__(self, name):
            self.diag = FakeDiag(name)

    # 1. Canonical PostgreSQL constraint matches
    err_pg_canonical = IntegrityError("duplicate key")
    err_pg_canonical.__cause__ = FakeCause('base_invoiceaddress_order_id_key')
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_pg_canonical) is True

    # 2. Legacy / unsupported constraint name has no repository evidence and does NOT match
    err_pg_legacy = IntegrityError("duplicate key")
    err_pg_legacy.__cause__ = FakeCause('pretixbase_invoiceaddress_order_id_key')
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_pg_legacy) is False

    # 3. Unrelated PostgreSQL constraints do NOT match (even if order_id is in message or name)
    err_pg_unrelated = IntegrityError("duplicate key for order_id")
    err_pg_unrelated.__cause__ = FakeCause('base_organizer_slug_key')
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_pg_unrelated) is False

    err_pg_other_order = IntegrityError("duplicate key for order_id")
    err_pg_other_order.__cause__ = FakeCause('base_orderposition_order_id_key')
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_pg_other_order) is False

    # 4. Exact SQLite invoice-address constraint matches
    err_sqlite_match = IntegrityError("UNIQUE constraint failed: base_invoiceaddress.order_id")
    err_sqlite_match.__cause__ = Exception()  # diag is None
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_sqlite_match) is True

    # SQLite error containing expected message plus unexpected extra text is rejected
    err_sqlite_extra_text = IntegrityError(
        "UNIQUE constraint failed: base_invoiceaddress.order_id and extra unexpected text"
    )
    err_sqlite_extra_text.__cause__ = Exception()  # diag is None
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_sqlite_extra_text) is False

    # 5. Unrelated SQLite unique constraint involving another table's order_id does NOT match
    err_sqlite_other_order = IntegrityError("UNIQUE constraint failed: base_orderposition.order_id")
    err_sqlite_other_order.__cause__ = Exception()  # diag is None
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_sqlite_other_order) is False

    # 6. Unrelated SQLite constraint does NOT match
    err_sqlite_unrelated = IntegrityError("UNIQUE constraint failed: base_organizer.slug")
    err_sqlite_unrelated.__cause__ = Exception()  # diag is None
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_sqlite_unrelated) is False

    # 7. Unknown diagnostic / error formats do NOT match
    err_unknown_msg = IntegrityError("unexpected internal database error occurred")
    err_unknown_msg.__cause__ = Exception()
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_unknown_msg) is False

    err_null_diag = IntegrityError("null value constraint failed")
    err_null_diag.__cause__ = FakeCause(None)
    assert OrderQuestionsViewMixin._is_invoice_order_unique_violation(err_null_diag) is False


@pytest.mark.django_db
def test_save_invoice_form_propagates_when_no_existing_address_found(modify_env, monkeypatch):
    """Verifies that if an order_id unique constraint IntegrityError occurs but no existing
    InvoiceAddress record can be found, the exception is re-raised rather than swallowed.
    """
    env = modify_env
    factory = RequestFactory()

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].delete()
        order_pk = env['order'].pk
        order = Order.objects.get(pk=order_pk)

        req = factory.post(
            '/',
            data={
                'name_parts_0': 'Some Name',
                'street': 'Some Street',
                'zipcode': '12345',
                'city': 'Some City',
                'country': 'DE',
            },
        )
        req.event = env['event']
        view = MockView(order, req)
        assert view.invoice_form.is_valid()

        def fail_save(*args, **kwargs):
            raise IntegrityError(
                'duplicate key value violates unique constraint "base_invoiceaddress_order_id_key"\n'
                'DETAIL: Key (order_id)=(999999) already exists.'
            )

        monkeypatch.setattr(view.invoice_form, 'save', fail_save)

        # Ensure no InvoiceAddress exists in DB
        assert InvoiceAddress.objects.filter(order=order).count() == 0

        with pytest.raises(IntegrityError, match="base_invoiceaddress_order_id_key"):
            with transaction.atomic():
                view.save_invoice_form()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_invalid_invoice_form_preserves_all_attendee_and_order_info(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    # country='INVALID' makes invoice_form invalid
    data = {
        'name_parts_0': 'New Invoicee',
        'street': 'New Street 42',
        'zipcode': '54321',
        'city': 'New City',
        'country': 'INVALID',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'updated1@dummy.test',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'updated2@dummy.test',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

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

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    # pos1 has invalid email
    data = {
        'name_parts_0': 'New Invoicee',
        'street': 'New Street 42',
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'invalid-email',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'updated2@dummy.test',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

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
def test_multiple_positions_one_invalid_leaves_no_positions_updated(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    # pos1 is valid, but pos2 has invalid email format
    data = {
        'name_parts_0': 'New Invoicee',
        'street': 'New Street 42',
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'updated1@dummy.test',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'invalid-email-pos2',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

    response = client.post(url, data, follow=False)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'We had difficulties processing your input' in content

    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'

        env['pos1'].refresh_from_db()
        # pos1 MUST NOT be updated even though pos1's form itself was valid!
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
def test_invalid_us_invoice_state_does_not_persist_attendee_changes(client, modify_env):
    """Reproduces issue #7676: US invoice address with empty state fails validation
    and must not persist attendee updates.
    """
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    data = {
        'name_parts_0': 'US Invoicee',
        'street': '123 Main Street',
        'zipcode': '90210',
        'city': 'Beverly Hills',
        'country': 'US',
        'state': '',  # required for US
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'updated1@dummy.test',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'updated2@dummy.test',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

    response = client.post(url, data, follow=False)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'We had difficulties processing your input' in content
    assert 'This field is required' in content

    with scope(event=env['event'], organizer=env['organizer']):
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'
        assert env['inv_addr'].country == 'DE'

        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Original Attendee 1'
        assert env['pos1'].attendee_email == 'att1@dummy.test'

        env['pos2'].refresh_from_db()
        assert env['pos2'].attendee_name == 'Original Attendee 2'
        assert env['pos2'].attendee_email == 'att2@dummy.test'

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
    # For presale modify, user must be authenticated as order owner
    client.force_login(env['user'])
    with scope(event=env['event'], organizer=env['organizer']):
        env['order'].email = env['user'].email
        env['order'].save()

    url = f"/{env['organizer'].slug}/{env['event'].slug}/order/{env['order'].code}/{env['order'].secret}/modify"

    data = {
        'name_parts_0': 'New Presale Invoicee',
        'street': '',  # invalid because invoice_address_required is True
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Presale Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'presale1@dummy.test',
        f"{env['pos1'].pk}-company": 'Presale Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Presale Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'presale2@dummy.test',
        f"{env['pos2'].pk}-company": 'Presale Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
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

    factory = RequestFactory()
    request = factory.post(
        '/',
        data={
            f"{env['pos1'].pk}-attendee_name_parts_0": 'Original Attendee 1',
            f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
            f"{env['pos1'].pk}-question_{new_q.pk}": 'Vegetarian',
            f"{env['pos2'].pk}-attendee_name_parts_0": 'Original Attendee 2',
            f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        },
    )
    request.event = env['event']

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

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
    with scope(event=env['event'], organizer=env['organizer']):
        q_file = Question.objects.create(
            event=env['event'],
            question='Passport Scan',
            type=Question.TYPE_FILE,
            required=False,
        )
        env['product'].questions.add(q_file)

        test_file = SimpleUploadedFile("passport.pdf", b"sample content", content_type="application/pdf")
        ans = QuestionAnswer.objects.create(
            orderposition=env['pos1'],
            question=q_file,
            file=test_file,
        )
        file_path = ans.file.name
        ans_pk = ans.pk

    assert default_storage.exists(file_path)

    factory = RequestFactory()

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

    # Case 1: Rollback retains the existing file
    req_clear = factory.post(
        '/',
        data={
            f"{env['pos1'].pk}-attendee_name_parts_0": 'Original Attendee 1',
            f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
            f"{env['pos1'].pk}-question_{q_file.pk}-clear": 'on',
            f"{env['pos2'].pk}-attendee_name_parts_0": 'Original Attendee 2',
            f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        },
    )
    req_clear.event = env['event']
    view1 = MockView(env['order'], req_clear)
    _ = view1.forms

    try:
        with transaction.atomic():
            view1.save()
            raise RuntimeError("Simulated failure after save")
    except RuntimeError:
        view1.cleanup_staged_uploads()

    # The file in storage must NOT have been deleted
    assert default_storage.exists(file_path)
    with scope(event=env['event'], organizer=env['organizer']):
        reloaded_ans = QuestionAnswer.objects.get(pk=ans_pk)
        assert reloaded_ans.file.name == file_path

    # Case 2: Commit deletes the file after on_commit callbacks run
    req_clear_commit = factory.post(
        '/',
        data={
            f"{env['pos1'].pk}-attendee_name_parts_0": 'Original Attendee 1',
            f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
            f"{env['pos1'].pk}-question_{q_file.pk}-clear": 'on',
            f"{env['pos2'].pk}-attendee_name_parts_0": 'Original Attendee 2',
            f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        },
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
    with scope(event=env['event'], organizer=env['organizer']):
        q_file = Question.objects.create(
            event=env['event'],
            question='Student ID',
            type=Question.TYPE_FILE,
            required=False,
        )
        env['product'].questions.add(q_file)

        orig_file = SimpleUploadedFile("id_old.pdf", b"old content", content_type="application/pdf")
        ans = QuestionAnswer.objects.create(
            orderposition=env['pos1'],
            question=q_file,
            file=orig_file,
        )
        old_file_path = ans.file.name
        ans_pk = ans.pk

    assert default_storage.exists(old_file_path)

    factory = RequestFactory()

    class MockView(OrderQuestionsViewMixin):
        def __init__(self, order, req):
            self.order = order
            self.request = req

    # Case 1: Replacement in rolled-back transaction cleans up staged upload and preserves old file
    new_uploaded_file1 = SimpleUploadedFile("id_new1.pdf", b"new content 1", content_type="application/pdf")
    req_replace_fail = factory.post(
        '/',
        data={
            f"{env['pos1'].pk}-attendee_name_parts_0": 'Original Attendee 1',
            f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
            f"{env['pos1'].pk}-question_{q_file.pk}": new_uploaded_file1,
            f"{env['pos2'].pk}-attendee_name_parts_0": 'Original Attendee 2',
            f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        },
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
            raise RuntimeError("Abort after upload")
    except RuntimeError:
        view1.cleanup_staged_uploads()

    # Staged file was deleted on cleanup, old file is still retained
    assert not default_storage.exists(staged_path)
    assert default_storage.exists(old_file_path)
    with scope(event=env['event'], organizer=env['organizer']):
        reloaded = QuestionAnswer.objects.get(pk=ans_pk)
        assert reloaded.file.name == old_file_path

    # Case 2: Replacement in committed transaction removes old file and retains new file
    new_uploaded_file2 = SimpleUploadedFile("id_new2.pdf", b"new content 2", content_type="application/pdf")
    req_replace_commit = factory.post(
        '/',
        data={
            f"{env['pos1'].pk}-attendee_name_parts_0": 'Original Attendee 1',
            f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
            f"{env['pos1'].pk}-question_{q_file.pk}": new_uploaded_file2,
            f"{env['pos2'].pk}-attendee_name_parts_0": 'Original Attendee 2',
            f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        },
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
