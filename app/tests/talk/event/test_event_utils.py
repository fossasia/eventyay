import pytest

from eventyay.base.models import Organizer as Organiser
from eventyay.event.utils import create_organizer_with_team as create_organiser_with_team


@pytest.mark.django_db
def test_user_organiser_init(user):
    assert Organiser.objects.count() == 0
    assert user.teams.count() == 0
    create_organiser_with_team(name="Name", slug="slug", users=[user])
    assert Organiser.objects.count() == 1
    assert user.teams.count() == 1
    assert user.teams.get().organiser == Organiser.objects.get()
