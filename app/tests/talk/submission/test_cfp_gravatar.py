import pytest
from django_scopes import scope
from eventyay.orga.forms.cfp import CfPSettingsForm


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
        # Build a minimal valid payload for CfPSettingsForm.
        # Only fields required for the form to be valid are listed explicitly;
        # cfp_enable_gravatar is the field under test.
        form_data = {
            'cfp_enable_gravatar': False,
        }

        # Test disabling Gravatar
        form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        if form.is_valid():
            form.save()
            assert not event.cfp.enable_gravatar
        else:
            pytest.fail(f"Form invalid: {form.errors}")

        # Test re-enabling Gravatar
        form_data['cfp_enable_gravatar'] = True
        form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        if form.is_valid():
            form.save()
            assert event.cfp.enable_gravatar
        else:
            pytest.fail(f"Form invalid: {form.errors}")
