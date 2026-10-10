import pytest
from django import forms
from django_scopes import scope

from eventyay.orga.forms.cfp import CfPFieldSettingsForm, CfPSettingsForm


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
def test_gravatar_owned_by_profile_picture_settings(event):
    """Test that Profile Picture settings owns Gravatar and CfPSettingsForm does not disable it."""
    with scope(event=event):
        # 1. Disable Gravatar through Profile Picture field settings
        field_form = CfPFieldSettingsForm(
            data={'enable_gravatar': False, 'label_0': 'Profile picture', 'help_text_0': ''},
            event=event,
            target='speaker',
            field_id='avatar',
        )
        assert field_form.is_valid(), field_form.errors
        field_form.save()
        event.refresh_from_db()
        assert not event.cfp.enable_gravatar

        # 2. Saving unrelated CFP Forms settings does NOT alter or disable Gravatar
        form_data = cfp_settings_form_data(event)
        settings_form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        assert settings_form.is_valid(), settings_form.errors
        settings_form.save()
        event.refresh_from_db()
        assert not event.cfp.enable_gravatar

        # 3. Enable Gravatar through Profile Picture field settings persists
        field_form = CfPFieldSettingsForm(
            data={'enable_gravatar': True, 'label_0': 'Profile picture', 'help_text_0': ''},
            event=event,
            target='speaker',
            field_id='avatar',
        )
        assert field_form.is_valid(), field_form.errors
        field_form.save()
        event.refresh_from_db()
        assert event.cfp.enable_gravatar

        # 4. Saving unrelated CFP Forms settings preserves enabled Gravatar
        form_data = cfp_settings_form_data(event)
        settings_form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        assert settings_form.is_valid(), settings_form.errors
        settings_form.save()
        event.refresh_from_db()
        assert event.cfp.enable_gravatar
