from io import BytesIO, StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils.timezone import now
from django_scopes import scope
from PIL import Image

from eventyay.base.models import Event, Organizer, Room
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


def test_a_failing_receiver_does_not_drop_other_targets(plugin_targets):
    def broken_receiver(sender, **kwargs):
        raise RuntimeError('plugin dependency missing')

    register_image_backfill_targets.connect(broken_receiver, dispatch_uid='test_backfill_broken_receiver')
    try:
        targets = get_image_targets()
    finally:
        register_image_backfill_targets.disconnect(dispatch_uid='test_backfill_broken_receiver')

    assert set(IMAGE_TARGETS) < set(targets)
    assert 'plugin_room_picture' in targets


def test_get_image_targets_does_not_change_core_targets(plugin_targets):
    get_image_targets()

    assert 'plugin_room_picture' not in IMAGE_TARGETS


@pytest.fixture
def room_with_picture(db):
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(organizer=organizer, name='Test Event', slug='test-event', date_from=now())
    buffer = BytesIO()
    Image.new('RGB', (60, 60), color='blue').save(buffer, format='PNG')
    with scope(event=event):
        room = Room.objects.create(event=event, name='Stage')
        room.picture.save('stage.png', ContentFile(buffer.getvalue()), save=True)
    return room


def dry_run(*args):
    out = StringIO()
    call_command('backfill_images', '--dry-run', '--min-size-kb', '0', *args, stdout=out)
    return out.getvalue()


def test_model_option_processes_a_plugin_target(plugin_targets, room_with_picture):
    output = dry_run('--model', 'plugin_room_picture')

    assert f'WOULD compress Room pk={room_with_picture.pk}' in output
    assert 'dry_run=1' in output


def test_a_target_accepted_by_model_option_is_processed_even_if_the_receiver_then_fails(room_with_picture):
    calls = []

    def flaky_receiver(sender, **kwargs):
        calls.append(sender)
        if len(calls) > 1:
            raise RuntimeError('plugin dependency missing')
        return {'flaky_room_picture': (Room, 'picture', False)}

    register_image_backfill_targets.connect(flaky_receiver, dispatch_uid='test_backfill_flaky_receiver')
    try:
        output = dry_run('--model', 'flaky_room_picture')
    finally:
        register_image_backfill_targets.disconnect(dispatch_uid='test_backfill_flaky_receiver')

    assert f'WOULD compress Room pk={room_with_picture.pk}' in output
    assert len(calls) == 1


def test_plugin_targets_are_processed_without_model_option(plugin_targets, room_with_picture):
    output = dry_run()

    # The picture is listed once for core's room target and once for the plugin's.
    assert output.count(f'WOULD compress Room pk={room_with_picture.pk}') == 2
