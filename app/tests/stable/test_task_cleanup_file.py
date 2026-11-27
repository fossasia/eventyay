from contextlib import contextmanager

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django_scopes import scope

from eventyay.base.models import CachedFile, Room, SpeakerInformation
from eventyay.common import tasks
from eventyay.common.tasks import task_cleanup_file


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def run_cleanup_now(monkeypatch, django_capture_on_commit_callbacks):
    """Run the cleanup jobs queued inside the block right away instead of sending them to Celery.

    Only FileCleanupMixin's callbacks are run, since other on-commit callbacks (like the room
    cache update) need services that aren't available in tests.
    """

    def apply_async(kwargs=None, **options):
        task_cleanup_file(**kwargs)

    monkeypatch.setattr(tasks.task_cleanup_file, 'apply_async', apply_async)

    @contextmanager
    def run():
        with django_capture_on_commit_callbacks() as callbacks:
            yield
        for callback in callbacks:
            if callback.__name__ == 'enqueue_cleanup':
                callback()

    return run


@pytest.mark.django_db
def test_replacing_speaker_information_resource_deletes_old_file(event, media_root, run_cleanup_now):
    with scope(event=event):
        info = SpeakerInformation.objects.create(event=event, title='Info', text='Text', target_group='accepted')
        info.resource.save('old.pdf', ContentFile(b'old'))
        old_name = info.resource.name

        with run_cleanup_now():
            info.resource.save('new.pdf', ContentFile(b'new'))

    assert not default_storage.exists(old_name)
    assert default_storage.exists(info.resource.name)


@pytest.mark.django_db
def test_replacing_room_picture_deletes_old_file(room, media_root, run_cleanup_now):
    with scope(event=room.event):
        room.picture.save('old.png', ContentFile(b'old'))
        old_name = room.picture.name

        with run_cleanup_now():
            room.picture.save('new.png', ContentFile(b'new'))

    assert not default_storage.exists(old_name)
    assert default_storage.exists(room.picture.name)


@pytest.mark.django_db
def test_replacing_picture_keeps_file_still_used_by_another_room(room, media_root, run_cleanup_now):
    with scope(event=room.event):
        room.picture.save('shared.png', ContentFile(b'shared'))
        shared_name = room.picture.name
        # Event.clone_from copies rooms like this, so both rooms point at the same file.
        copy = Room.objects.get(pk=room.pk)
        copy.pk = None
        copy.save()

        with run_cleanup_now():
            copy.picture.save('new.png', ContentFile(b'new'))

        room.refresh_from_db()
    assert room.picture.name == shared_name
    assert default_storage.exists(shared_name)


@pytest.mark.django_db
def test_cleanup_skips_job_without_file_name(room, media_root):
    with scope(event=room.event):
        room.picture.save('old.png', ContentFile(b'old'))
        old_name = room.picture.name
        old_path = room.picture.path
        Room.objects.filter(pk=room.pk).update(picture='new.png')

    # Jobs queued before file_name was added only have the path.
    task_cleanup_file(model='base.Room', pk=room.pk, field='picture', path=old_path)

    assert default_storage.exists(old_name)


@pytest.mark.django_db
@pytest.mark.parametrize('model', ['Room', 'base.DoesNotExist'])
def test_cleanup_ignores_unknown_models(room, media_root, model):
    with scope(event=room.event):
        room.picture.save('old.png', ContentFile(b'old'))
        old_name = room.picture.name
        old_path = room.picture.path
        Room.objects.filter(pk=room.pk).update(picture='new.png')

    task_cleanup_file(model=model, pk=room.pk, field='picture', path=old_path, file_name=old_name)

    assert default_storage.exists(old_name)


@pytest.mark.django_db
def test_cleanup_ignores_models_without_the_mixin(media_root):
    # CachedFile has a real file field but doesn't use FileCleanupMixin, so only the
    # mixin check stops this job from deleting the file.
    cached_file = CachedFile.objects.create(filename='current.txt', type='text/plain')
    cached_file.file.save('current.txt', ContentFile(b'current'))
    old_name = default_storage.save('old.txt', ContentFile(b'old'))

    task_cleanup_file(
        model='base.CachedFile',
        pk=cached_file.pk,
        field='file',
        path=default_storage.path(old_name),
        file_name=old_name,
    )

    assert default_storage.exists(old_name)


@pytest.mark.django_db
@pytest.mark.parametrize('field', ['does_not_exist', 'name'])
def test_cleanup_ignores_fields_that_are_not_file_fields(room, media_root, field):
    with scope(event=room.event):
        room.picture.save('old.png', ContentFile(b'old'))
        old_name = room.picture.name
        old_path = room.picture.path
        Room.objects.filter(pk=room.pk).update(picture='new.png')

    task_cleanup_file(model='base.Room', pk=room.pk, field=field, path=old_path, file_name=old_name)

    assert default_storage.exists(old_name)


@pytest.mark.django_db
def test_cleanup_skips_job_whose_path_does_not_match_file_name(room, media_root):
    with scope(event=room.event):
        room.picture.save('old.png', ContentFile(b'old'))
        old_name = room.picture.name
        old_path = room.picture.path
        Room.objects.filter(pk=room.pk).update(picture='new.png')

    task_cleanup_file(model='base.Room', pk=room.pk, field='picture', path=old_path, file_name='other.png')

    assert default_storage.exists(old_name)
