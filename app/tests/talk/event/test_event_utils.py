import pytest

from eventyay.base.models.organizer import Organizer
from eventyay.event.utils import create_organizer_with_team


@pytest.mark.django_db
def test_user_organiser_init(user):
    assert Organizer.objects.count() == 0
    assert user.teams.count() == 0
    create_organizer_with_team(name="Name", slug="slug", users=[user])
    assert Organizer.objects.count() == 1
    assert user.teams.count() == 1
    assert user.teams.get().organizer == Organizer.objects.get()
