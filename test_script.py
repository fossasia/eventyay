import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventyay.settings")
django.setup()

from eventyay.person.forms.profile import SpeakerProfileForm
from eventyay.base.models import User, Event

# Find an event or user
event = Event.objects.first()
user = User.objects.create(email=None, locale="en", timezone="UTC")
profile = user.event_profile(event)

# Bound form without email
form = SpeakerProfileForm(
    data={'fullname': 'Test', 'no_email': 'on'},
    event=event,
    user=user,
    allow_no_email=True,
    ignore_first_time_exclude=True,
)
print("Is valid?", form.is_valid())
if not form.is_valid():
    print("Errors:", form.errors)
else:
    form.save()
    print("User email:", user.email)
