from io import StringIO

import pytest
from django.core.management import call_command

from eventyay.base.models import Room
from eventyay.base.signals import register_image_backfill_targets
from eventyay.common.management.commands.backfill_images import IMAGE_TARGETS, get_image_targets


def test_backfill_includes_remaining_image_fields():
    assert IMAGE_TARGETS['user'][1:] == ('avatar', True)
    assert IMAGE_TARGETS['profile_picture'][1:] == ('profile_picture', True)
    assert IMAGE_TARGETS['event_logo'][1] == 'logo'
    assert IMAGE_TARGETS['event_header_image'][1] == 'header_image'
    assert IMAGE_TARGETS['question_answer'][1] == 'answer_file'
    assert IMAGE_TARGETS['question_answer'][3] is True
    assert IMAGE_TARGETS['ticket_question_answer'][1] == 'file'
    assert IMAGE_TARGETS['ticket_question_answer'][3] is True


@pytest.fixture
def plugin_targets():
    def receiver(sender, **kwargs):
        return {
            'plugin_room_picture': (Room, 'picture', False),
            'event_logo': (Room, 'picture', False),
            'settings': (Room, 'picture', False),
        }

    register_image_backfill_targets.connect(receiver, dispatch_uid='test_backfill_plugin_targets')
    yield
    register_image_backfill_targets.disconnect(dispatch_uid='test_backfill_plugin_targets')


def test_plugins_can_register_image_targets(plugin_targets):
    targets = get_image_targets()

    assert targets['plugin_room_picture'] == (Room, 'picture', False)
    # A plugin can't replace a core target or the settings pass.
    assert targets['event_logo'] == IMAGE_TARGETS['event_logo']
    assert 'settings' not in targets
    assert set(IMAGE_TARGETS) < set(targets)


def test_get_image_targets_does_not_change_core_targets(plugin_targets):
    get_image_targets()

    assert 'plugin_room_picture' not in IMAGE_TARGETS


@pytest.mark.django_db
def test_model_option_accepts_plugin_targets(plugin_targets):
    out = StringIO()

    call_command('backfill_images', '--dry-run', '--model', 'plugin_room_picture', stdout=out)

    assert 'Done.' in out.getvalue()
