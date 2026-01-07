import pytest
from django.utils.timezone import now
from eventyay.base.models import Event, Organizer, User, Team
from eventyay.cfp.flow import ProfileStep
from eventyay.person.forms import SpeakerProfileForm

@pytest.mark.django_db
def test_cfs_profile_step_execution_with_invalid_data():
    """
    Test that ProfileStep.done() raises an error or handles invalid data gracefully.
    Currently, it might crash with 500 if form is invalid.
    """
    # Setup
    organizer = Organizer.objects.create(name='Org', slug='org')
    event = Event.objects.create(
        organizer=organizer, name='Event', slug='event',
        date_from=now(), date_to=now()
    )
    user = User.objects.create_user(email='test@example.com', password='password')
    
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
    
    # Simulate invalid form data (empty required fields if any, or just empty POST)
    # Profile form usually requires fullname if it's in the form
    # Let's say we pass empty data
    request.POST = {} 

    # Execute done()
    from django_scopes import scope
    try:
        with scope(event=event):
            step.done(request)
    except Exception as e:
        import traceback
        traceback.print_exc()
        pytest.fail(f"ProfileStep.done raised exception: {e}")

    # If it didn't fail, check if it saved invalid data? 
    # But the bug report says it returns HTTP 500, which usually implies an unhandled exception.
