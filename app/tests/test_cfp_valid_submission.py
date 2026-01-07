import pytest
from django.utils.timezone import now
from eventyay.base.models import Event, Organizer, User, SpeakerProfile
from eventyay.cfp.flow import ProfileStep
from django_scopes import scope

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass

@pytest.mark.django_db
def test_cfs_profile_step_valid_submission_loop():
    """
    Test that a valid submission passes is_completed() check.
    """
    # Setup
    organizer = Organizer.objects.create(name='Org', slug='org')
    event = Event.objects.create(
        organizer=organizer, name='Event', slug='event',
        date_from=now(), date_to=now()
    )
    user = User.objects.create_user(email='test@example.com', password='password', fullname='Test User')
    
    # Create request mock
    from django.test import RequestFactory
    factory = RequestFactory()
    request = factory.post('/submit/profile/')
    request.user = user
    request.event = event
    
    class MockResolverMatch:
        kwargs = {'tmpid': 'testtmpid'}
    request.resolver_match = MockResolverMatch()

    class MockSession(dict):
        modified = False
    
    request.session = MockSession({'cfp': {}})

    # Initialize Step
    step = ProfileStep(event=event)
    step.request = request
    
    # Simulate VALID form data
    data = {
        'fullname': 'Test User',
        'email': 'test@example.com',
        'biography': 'My Bio',
        'availabilities': '[]', # JSON string for availabilities
        'action': 'submit'
    }
    # Re-create request with data
    request = factory.post('/submit/profile/', data=data)
    request.user = user
    request.event = event
    request.resolver_match = MockResolverMatch()
    request.session = MockSession({'cfp': {}})
    step.request = request

    from django_scopes import scope
    try:
        with scope(event=event):
             # 1. Simulate the POST logic manually to check internal state
            form = step.get_form()
            
            assert form.is_valid(), f"Form should be valid but has errors: {form.errors}"
            
            step.set_data(form.cleaned_data)
            
            # 2. Key Check: is_completed()
            # This reconstructs form from session data
            is_complete = step.is_completed(request)
            
            if not is_complete:
                bound_form = step.get_form(from_storage=True)
                bound_form.is_valid()
                
            assert is_complete, "Profile step should be completed after valid submission"

    except Exception as e:
        import traceback
        traceback.print_exc()
        pytest.fail(f"Test failed with exception: {e}")
