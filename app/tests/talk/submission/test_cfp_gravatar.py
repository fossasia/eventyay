import pytest
from eventyay.base.models import CfP
from eventyay.orga.forms.cfp import CfPSettingsForm

@pytest.mark.django_db
def test_cfp_enable_gravatar_default_true(event):
    """Test that enable_gravatar defaults to True when not set"""
    # Event fixture creates an event. Check if it has CfP.
    if not hasattr(event, 'cfp'):
        CfP.objects.create(event=event)
    
    cfp = event.cfp
    # Should default to True
    assert cfp.enable_gravatar

@pytest.mark.django_db
def test_cfp_enable_gravatar_explicit_false(event):
    """Test that enable_gravatar can be explicitly set to False"""
    if not hasattr(event, 'cfp'):
        CfP.objects.create(event=event)
    
    cfp = event.cfp
    cfp.settings['cfp_enable_gravatar'] = False
    cfp.save()
    
    # Should return False when explicitly set
    assert not cfp.enable_gravatar

@pytest.mark.django_db
def test_cfp_enable_gravatar_explicit_true(event):
    """Test that enable_gravatar can be explicitly set to True"""
    if not hasattr(event, 'cfp'):
        CfP.objects.create(event=event)
    
    cfp = event.cfp
    cfp.settings['cfp_enable_gravatar'] = True
    cfp.save()
    
    # Should return True when explicitly set
    assert cfp.enable_gravatar

@pytest.mark.django_db
def test_cfp_enable_gravatar_missing_key(event):
    """Test enable_gravatar behavior when key is missing from settings"""
    if not hasattr(event, 'cfp'):
        CfP.objects.create(event=event)
    
    cfp = event.cfp
    
    # Ensure key doesn't exist
    if 'cfp_enable_gravatar' in cfp.settings:
        del cfp.settings['cfp_enable_gravatar']
        cfp.save()
    
    # Should still default to True
    assert cfp.enable_gravatar

@pytest.mark.django_db
def test_cfp_settings_form_toggle_gravatar(event):
    """Test that CfPSettingsForm correctly updates enable_gravatar setting"""
    from django_scopes import scope
    
    if not hasattr(event, 'cfp'):
        CfP.objects.create(event=event)
    
    cfp = event.cfp
    
    with scope(event=event):
        # Instantiate form to get fields and initial values
        form_inst = CfPSettingsForm(obj=event, read_only=False)
        form_data = {}
        
        # Populate data for all fields, especially required ones
        for name, field in form_inst.fields.items():
            # Prefer explicit initial data
            if name in form_inst.initial:
                form_data[name] = form_inst.initial[name]
            # Then field-level initial
            elif field.initial is not None:
                 form_data[name] = field.initial
            # Then first choice for ChoiceFields (if required)
            elif field.required and hasattr(field, 'choices') and field.choices:
                 form_data[name] = field.choices[0][0]
            # Then boolean defaults
            elif isinstance(field, (pytest.importorskip("django.forms").BooleanField)):
                 form_data[name] = False

        # Test setting to False
        form_data['cfp_enable_gravatar'] = False

        form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        
        if form.is_valid():
            form.save()
            assert not cfp.enable_gravatar
        else:
            pytest.fail(f"Form invalid: {form.errors}")
        
        # Test setting back to True
        form_data['cfp_enable_gravatar'] = True
        form = CfPSettingsForm(obj=event, read_only=False, data=form_data)
        
        if form.is_valid():
            form.save()
            assert cfp.enable_gravatar
        else:
            pytest.fail(f"Form invalid: {form.errors}")
