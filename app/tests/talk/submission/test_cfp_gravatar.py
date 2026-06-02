import pytest
from django import forms
from django_scopes import scope
from eventyay.orga.forms.cfp import CfPSettingsForm


def cfp_settings_form_data(event, **overrides):
    form = CfPSettingsForm(obj=event, read_only=False)
    data = {}
    for name, field in form.fields.items():
        initial = form.initial.get(name, field.initial)
        if isinstance(field, forms.BooleanField):
            data[name] = bool(initial)
        else:
            data[name] = initial if initial is not None else ''
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_cfp_enable_gravatar_default_true(event):
    """Test that enable_gravatar is enabled in the default CFP settings."""
    cfp = event.cfp
    assert cfp.enable_gravatar


@pytest.mark.django_db
def test_cfp_enable_gravatar_explicit_false(event):
    """Test that enable_gravatar can be explicitly set to False."""
    cfp = event.cfp
    cfp.settings['cfp_enable_gravatar'] = False
    cfp.save()

    assert not cfp.enable_gravatar


@pytest.mark.django_db
def test_cfp_enable_gravatar_explicit_true(event):
    """Test that enable_gravatar can be explicitly set to True."""
    cfp = event.cfp
    cfp.settings['cfp_enable_gravatar'] = True
    cfp.save()

    assert cfp.enable_gravatar


@pytest.mark.django_db
def test_cfp_enable_gravatar_missing_key(event):
    """Test enable_gravatar defaults to True when key is absent from settings."""
    cfp = event.cfp

    if 'cfp_enable_gravatar' in cfp.settings:
        del cfp.settings['cfp_enable_gravatar']
        cfp.save()

    assert cfp.enable_gravatar


@pytest.mark.django_db
def test_cfp_settings_form_toggle_gravatar(event):
    """Test that CfPSettingsForm correctly updates enable_gravatar setting."""
    with scope(event=event):
        # Test disabling Gravatar
        form_data = cfp_settings_form_data(event, cfp_enable_gravatar=False)
        form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        if form.is_valid():
            form.save()
            assert not event.cfp.enable_gravatar
        else:
            pytest.fail(f"Form invalid: {form.errors}")

        # Test re-enabling Gravatar
        form_data = cfp_settings_form_data(event, cfp_enable_gravatar=True)
        form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        if form.is_valid():
            form.save()
            assert event.cfp.enable_gravatar
        else:
            pytest.fail(f"Form invalid: {form.errors}")
