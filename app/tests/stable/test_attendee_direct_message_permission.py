import pytest

from eventyay.base.models.auth import User
from eventyay.core.permissions import Permission
from eventyay.eventyay_common.video.permissions import video_attendee_trait


@pytest.mark.django_db
def test_attendee_gets_direct_message_permission(event):
    user = User.objects.create(
        event=event,
        profile={},
        traits=['attendee', video_attendee_trait(event.slug)],
    )
    perms = event.get_all_permissions(user)[event]
    assert Permission.EVENT_CHAT_DIRECT in perms


@pytest.mark.django_db
def test_attendee_without_admin_trait_keeps_direct_message(event):
    user = User.objects.create(
        event=event,
        profile={},
        traits=['attendee', video_attendee_trait(event.slug)],
    )
    perms = event.get_all_permissions(user)[event]
    assert Permission.EVENT_CHAT_DIRECT in perms
