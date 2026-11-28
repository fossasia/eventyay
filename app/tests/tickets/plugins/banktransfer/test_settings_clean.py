import pytest
from django.core.exceptions import ValidationError
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer
from eventyay.control.forms.event import ProviderForm
from eventyay.plugins.banktransfer.payment import BankTransfer

TYPE_KEY = 'payment_banktransfer_bank_details_type'
DETAILS_KEY = 'payment_banktransfer_bank_details'
ENABLED_KEY = 'payment_banktransfer__enabled'
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
    event.settings.locales = ['en']
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


def make_provider_form(provider, data):
    prefix = provider.settings.get_prefix()

    form = ProviderForm(
        obj=provider.event,
        settingspref=prefix,
        data=data,
        provider=provider,
    )

    form.fields = {
        f'{prefix}{key}': field
        for key, field in provider.settings_form_fields.items()
    }

    form.prepare_fields()
    return form


@pytest.mark.django_db
@pytest.mark.parametrize('enabled', [True, False])
def test_payment_settings_sepa_missing_fields(provider, enabled):
    form = make_provider_form(
        provider,
        {
            ENABLED_KEY: enabled,
            TYPE_KEY: 'sepa',
            'payment_banktransfer_ack': True,
        },
    )

    assert not form.is_valid()
    assert SEPA_KEYS.issubset(form.errors)


@pytest.mark.django_db
@pytest.mark.parametrize('enabled', [True, False])
def test_payment_settings_other_missing_details(provider, enabled):
    form = make_provider_form(
        provider,
        {
            ENABLED_KEY: enabled,
            TYPE_KEY: 'other',
            'payment_banktransfer_ack': True,
        },
    )

    assert not form.is_valid()
    assert DETAILS_KEY in form.errors


@pytest.mark.django_db
def test_payment_settings_sepa_valid_details(provider):
    form = make_provider_form(
        provider,
        {
            ENABLED_KEY: True,
            'payment_banktransfer__restrict_to_sales_channels': ['web'],
            TYPE_KEY: 'sepa',
            'payment_banktransfer_ack': True,
            'payment_banktransfer_bank_details_sepa_name': 'Jane Doe',
            'payment_banktransfer_bank_details_sepa_iban': 'DE89370400440532013000',
            'payment_banktransfer_bank_details_sepa_bic': 'COBADEFFXXX',
            'payment_banktransfer_bank_details_sepa_bank': 'Example Bank',
        },
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_payment_settings_other_valid_details(provider):
    locale_index = provider.settings_form_fields[
        'bank_details'
    ].widget.locales.index('en')

    form = make_provider_form(
        provider,
        {
            ENABLED_KEY: True,
            'payment_banktransfer__restrict_to_sales_channels': ['web'],
            TYPE_KEY: 'other',
            'payment_banktransfer_ack': True,
            f'{DETAILS_KEY}_{locale_index}': 'Account 1234, routing 5678',
        },
    )

    assert form.is_valid(), form.errors
