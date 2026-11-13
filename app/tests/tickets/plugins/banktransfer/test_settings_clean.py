import pytest
from django.core.exceptions import ValidationError
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer
from eventyay.plugins.banktransfer.payment import BankTransfer

TYPE_KEY = 'payment_banktransfer_bank_details_type'
DETAILS_KEY = 'payment_banktransfer_bank_details'
SEPA_KEYS = {
    'payment_banktransfer_bank_details_sepa_name',
    'payment_banktransfer_bank_details_sepa_iban',
    'payment_banktransfer_bank_details_sepa_bic',
    'payment_banktransfer_bank_details_sepa_bank',
}


@pytest.fixture
def provider():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='eventyay.plugins.banktransfer',
    )
    return BankTransfer(event)


@pytest.mark.django_db
def test_sepa_reports_all_missing_fields_at_once(provider):
    with pytest.raises(ValidationError) as exc:
        provider.settings_form_clean({TYPE_KEY: 'sepa'})
    assert set(exc.value.error_dict) == SEPA_KEYS


@pytest.mark.django_db
def test_sepa_reports_only_the_missing_fields(provider):
    cleaned_data = {
        TYPE_KEY: 'sepa',
        'payment_banktransfer_bank_details_sepa_name': 'Jane Doe',
        'payment_banktransfer_bank_details_sepa_iban': 'DE89370400440532013000',
    }
    with pytest.raises(ValidationError) as exc:
        provider.settings_form_clean(cleaned_data)
    assert set(exc.value.error_dict) == {
        'payment_banktransfer_bank_details_sepa_bic',
        'payment_banktransfer_bank_details_sepa_bank',
    }


@pytest.mark.django_db
def test_sepa_with_all_fields_passes(provider):
    cleaned_data = {
        TYPE_KEY: 'sepa',
        'payment_banktransfer_bank_details_sepa_name': 'Jane Doe',
        'payment_banktransfer_bank_details_sepa_iban': 'DE89370400440532013000',
        'payment_banktransfer_bank_details_sepa_bic': 'COBADEFFXXX',
        'payment_banktransfer_bank_details_sepa_bank': 'Example Bank',
    }
    assert provider.settings_form_clean(cleaned_data) == cleaned_data


@pytest.mark.django_db
def test_other_account_requires_bank_details(provider):
    with pytest.raises(ValidationError) as exc:
        provider.settings_form_clean({TYPE_KEY: 'other'})
    assert set(exc.value.error_dict) == {DETAILS_KEY}


@pytest.mark.django_db
def test_other_account_with_details_passes(provider):
    cleaned_data = {TYPE_KEY: 'other', DETAILS_KEY: 'Account 1234, routing 5678'}
    assert provider.settings_form_clean(cleaned_data) == cleaned_data