import pytest
from django import forms
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Organizer
from eventyay.control.forms.event import (
    EventUpdateForm,
    InvoiceSettingsForm,
    apply_searchable_select_attrs,
)


@pytest.fixture
def event_obj():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy Org', slug='dummy-org')
        event = Event.objects.create(
            organizer=organizer,
            name='Dummy Event',
            slug='dummy-event',
            date_from=now(),
            currency='EUR',
        )
    return event


def test_apply_searchable_select_attrs_preserves_existing_classes():
    field = forms.ChoiceField(
        choices=[('a', 'A')],
        widget=forms.Select(attrs={'class': 'custom-select-class'}),
    )
    apply_searchable_select_attrs(field)
    classes = field.widget.attrs['class'].split()
    assert 'custom-select-class' in classes
    assert 'form-control' in classes
    assert field.widget.attrs['data-searchable-select'] == ''
    assert field.widget.attrs['data-search-placeholder'] == 'Search'
    assert field.widget.attrs['data-empty-text'] == 'No results'


def test_apply_searchable_select_attrs_does_not_duplicate_form_control():
    field = forms.ChoiceField(
        choices=[('a', 'A')],
        widget=forms.Select(attrs={'class': 'form-control other-class'}),
    )
    apply_searchable_select_attrs(field)
    classes = field.widget.attrs['class'].split()
    assert classes.count('form-control') == 1
    assert 'other-class' in classes


@pytest.mark.django_db
def test_event_update_form_currency_is_searchable(event_obj):
    with scope(organizer=event_obj.organizer):
        form = EventUpdateForm(instance=event_obj)
        currency_widget = form.fields['currency'].widget
        attrs = currency_widget.attrs
        assert 'data-searchable-select' in attrs
        assert attrs['data-search-placeholder'] == 'Search'
        assert attrs['data-empty-text'] == 'No results'
        assert 'form-control' in attrs.get('class', '').split()


@pytest.mark.django_db
def test_invoice_settings_form_country_is_searchable(event_obj):
    with scope(organizer=event_obj.organizer):
        form = InvoiceSettingsForm(obj=event_obj)
        country_widget = form.fields['invoice_address_from_country'].widget
        attrs = country_widget.attrs
        assert 'data-searchable-select' in attrs
        assert attrs['data-search-placeholder'] == 'Search'
        assert attrs['data-empty-text'] == 'No results'
        assert 'form-control' in attrs.get('class', '').split()


def test_searchable_select_js_placeholder_logic():
    from pathlib import Path

    js_file = Path(__file__).resolve().parents[3] / 'eventyay' / 'static' / 'common' / 'js' / 'searchable-select.js'
    css_file = Path(__file__).resolve().parents[3] / 'eventyay' / 'static' / 'common' / 'css' / 'searchable-select.css'

    with open(js_file, 'r', encoding='utf-8') as f:
        js = f.read()

    # Verifies syncLabel distinguishes empty-valued allLabel options from placeholders
    assert "const isPlaceholder = Boolean(selected && selected.value === '' && !allLabel)" in js
    assert "toggle.classList.toggle('has-placeholder', isPlaceholder)" in js
    assert "root.classList.toggle('has-placeholder', isPlaceholder)" in js

    with open(css_file, 'r', encoding='utf-8') as f:
        css = f.read()

    # Verifies placeholder muted styling rule
    assert '.searchable-select.has-placeholder .searchable-select__value' in css
    assert 'var(--color-text-muted, #777)' in css

