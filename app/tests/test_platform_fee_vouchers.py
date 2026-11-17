import datetime
from decimal import Decimal

import pytest
from django import forms
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, User
from eventyay.base.models.auth import StaffSession
from eventyay.base.models.vouchers import InvoiceVoucher
from eventyay.control.signals import (
    platform_fee_voucher_copied,
    platform_fee_voucher_forms,
    platform_fee_voucher_targets,
)
from eventyay.eventyay_common.tasks import calculate_ticket_fee


class PlanTargetForm(forms.Form):
    plan = forms.BooleanField(required=False)

    saved_for = []

    def has_targets(self):
        return self.cleaned_data['plan']

    def save(self, voucher):
        self.saved_for.append((voucher.pk, self.cleaned_data['plan']))


@pytest.fixture
def admin_client(client, db):
    admin = User.objects.create_adminuser(email='admin@example.com', password='admin-pass')
    client.force_login(admin)
    session = client.session
    session.save()
    StaffSession.objects.create(user=admin, session_key=session.session_key)
    return client


@pytest.fixture
def plan_target_form():
    def receiver(sender, request, voucher, **kwargs):
        return PlanTargetForm(data=request.POST or None, prefix='plantarget')

    PlanTargetForm.saved_for = []
    platform_fee_voucher_forms.connect(receiver, dispatch_uid='test_plan_target_form')
    yield PlanTargetForm
    platform_fee_voucher_forms.disconnect(dispatch_uid='test_plan_target_form')


def voucher_post_data(**overrides):
    valid_until = now() + datetime.timedelta(days=30)
    data = {
        'code': 'PLANVOUCHER1',
        'status': InvoiceVoucher.STATUS_ACTIVE,
        'valid_until_0': f'{valid_until:%Y-%m-%d}',
        'valid_until_1': '12:00:00',
        'comment': '',
        'waiver_type': 'percent',
        'value': '25.00',
        'max_usages': '5',
        'budget': '',
        'scope_type': 'platform_wide',
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_voucher_form_saves_plugin_form(admin_client, plan_target_form):
    response = admin_client.post(
        reverse('eventyay_admin:admin.vouchers.add'),
        voucher_post_data(**{'plantarget-plan': 'on'}),
    )

    assert response.status_code == 302
    voucher = InvoiceVoucher.objects.get(code='PLANVOUCHER1')
    assert voucher.applies_to_platform_fees is False
    assert plan_target_form.saved_for == [(voucher.pk, True)]


@pytest.mark.django_db
def test_voucher_form_renders_plugin_form(admin_client, plan_target_form):
    response = admin_client.get(reverse('eventyay_admin:admin.vouchers.add'))

    assert response.status_code == 200
    assert 'name="plantarget-plan"' in response.content.decode()


@pytest.mark.django_db
def test_active_voucher_must_apply_to_something(admin_client, plan_target_form):
    response = admin_client.post(reverse('eventyay_admin:admin.vouchers.add'), voucher_post_data())

    assert response.status_code == 200
    assert not InvoiceVoucher.objects.filter(code='PLANVOUCHER1').exists()
    assert 'must apply to ticket platform fees' in response.content.decode()
    assert plan_target_form.saved_for == []


@pytest.mark.django_db
def test_platform_fee_voucher_needs_no_plugin_target(admin_client, plan_target_form):
    response = admin_client.post(
        reverse('eventyay_admin:admin.vouchers.add'),
        voucher_post_data(applies_to_platform_fees='on'),
    )

    assert response.status_code == 302
    assert InvoiceVoucher.objects.get(code='PLANVOUCHER1').applies_to_platform_fees is True


@pytest.mark.django_db
def test_voucher_detail_lists_targets(admin_client):
    voucher = InvoiceVoucher.objects.create(code='DETAILS1', price_mode='percent', value=Decimal('10.00'))

    def receiver(sender, voucher, **kwargs):
        return ['Plans: Pro']

    platform_fee_voucher_targets.connect(receiver, dispatch_uid='test_voucher_targets')
    try:
        response = admin_client.get(reverse('eventyay_admin:admin.voucher.detail', kwargs={'voucher': voucher.pk}))
    finally:
        platform_fee_voucher_targets.disconnect(dispatch_uid='test_voucher_targets')

    content = response.content.decode()
    assert 'Ticket platform fees' in content
    assert 'Plans: Pro' in content


@pytest.mark.django_db
def test_duplicate_voucher_notifies_plugins(admin_client):
    voucher = InvoiceVoucher.objects.create(
        code='ORIGINAL1', price_mode='percent', value=Decimal('10.00'), applies_to_platform_fees=False
    )
    copies = []

    def receiver(sender, source, voucher, **kwargs):
        copies.append((source.pk, voucher.pk))

    platform_fee_voucher_copied.connect(receiver, dispatch_uid='test_voucher_copied')
    try:
        admin_client.post(reverse('eventyay_admin:admin.voucher.duplicate', kwargs={'voucher': voucher.pk}))
    finally:
        platform_fee_voucher_copied.disconnect(dispatch_uid='test_voucher_copied')

    duplicate = InvoiceVoucher.objects.exclude(pk=voucher.pk).get()
    assert duplicate.applies_to_platform_fees is False
    assert copies == [(voucher.pk, duplicate.pk)]


@pytest.mark.django_db
def test_budget_tracks_usage():
    voucher = InvoiceVoucher.objects.create(
        code='BUDGET01', price_mode='percent', value=Decimal('50.00'), budget=Decimal('20.00'), max_usages=10
    )
    assert voucher.remaining_budget() == Decimal('20.00')
    assert voucher.get_budget_display() == '0.00 / 20.00'

    voucher.budget_used = Decimal('20.00')
    assert voucher.remaining_budget() == Decimal('0.00')
    assert voucher.is_active() is False
    assert voucher.computed_status == 'used_up'


@pytest.mark.django_db
def test_ticket_fee_respects_platform_fee_flag_and_budget():
    organizer = Organizer.objects.create(name='Org', slug='org')
    event = Event.objects.create(
        organizer=organizer, name='Event', slug='event', date_from=now(), currency='EUR'
    )
    voucher = InvoiceVoucher.objects.create(
        code='TICKETFEE1', price_mode='percent', value=Decimal('100.00'), budget=Decimal('3.00'), max_usages=5
    )

    _fee, final_fee, discount = calculate_ticket_fee(Decimal('1000.00'), Decimal('1.00'), event, voucher)
    assert discount == Decimal('3.00')
    assert final_fee == Decimal('7.00')

    voucher.applies_to_platform_fees = False
    _fee, final_fee, discount = calculate_ticket_fee(Decimal('1000.00'), Decimal('1.00'), event, voucher)
    assert discount == Decimal('0.00')
    assert final_fee == Decimal('10.00')


@pytest.mark.django_db
def test_duplicate_voucher_rolls_back_when_plugin_copy_fails(admin_client):
    voucher = InvoiceVoucher.objects.create(code='ORIGINAL2', price_mode='percent', value=Decimal('10.00'))

    def receiver(sender, source, voucher, **kwargs):
        raise RuntimeError('plugin copy failed')

    platform_fee_voucher_copied.connect(receiver, dispatch_uid='test_voucher_copy_fails')
    try:
        with pytest.raises(RuntimeError):
            admin_client.post(reverse('eventyay_admin:admin.voucher.duplicate', kwargs={'voucher': voucher.pk}))
    finally:
        platform_fee_voucher_copied.disconnect(dispatch_uid='test_voucher_copy_fails')

    assert list(InvoiceVoucher.objects.values_list('code', flat=True)) == ['ORIGINAL2']
