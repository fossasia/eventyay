import pytest
from eventyay.schedule.forms import RoomForm
from eventyay.base.models import Room

@pytest.mark.django_db
def test_room_form_name_required(event):
    """
    Verify that the 'name' field in RoomForm is required.
    This ensures that the 'Optional' label is not displayed in the UI.
    """
    # Test with empty name
    form = RoomForm(event=event, instance=Room(event=event), data={
        'name': '',
        'guid': '',
        'description': 'Test Room',
        'speaker_info': 'Test Info',
        'capacity': 100,
    })
    
    # name is required, so the form should be invalid
    assert form.is_valid() is False
    assert 'name' in form.errors
    assert form.fields['name'].required is True

@pytest.mark.django_db
def test_room_form_valid_with_name(event):
    """
    Verify that the RoomForm is valid when a name is provided.
    """
    form = RoomForm(event=event, instance=Room(event=event), data={
        'name': 'Great Hall',
        'guid': '',
        'description': 'Test Room',
        'speaker_info': 'Test Info',
        'capacity': 100,
    })
    
    assert form.is_valid() is True
    assert 'name' not in form.errors
