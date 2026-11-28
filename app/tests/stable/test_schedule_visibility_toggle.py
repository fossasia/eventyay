import pytest
from django_scopes import scope

from eventyay.base.models import Event


@pytest.mark.django_db
def test_toggle_schedule_visibility_saves_locally_without_sync_task(organizer_client, event, monkeypatch):
    applied_tasks = []
    monkeypatch.setattr(
        'celery.app.task.Task.apply_async',
        lambda *args, **kwargs: applied_tasks.append((args, kwargs)),
    )

    with scope(event=event):
        assert event.get_feature_flag('show_schedule') is True

    response = organizer_client.post(event.orga_urls.toggle_schedule)
    assert response.status_code == 302
    assert response.url == event.orga_urls.schedule
    event = Event.objects.get(pk=event.pk)
    with scope(event=event):
        assert event.feature_flags['show_schedule'] is False
        assert event.settings.talk_schedule_public is False

    response = organizer_client.post(event.orga_urls.toggle_schedule)
    assert response.status_code == 302
    assert response.url == event.orga_urls.schedule
    event = Event.objects.get(pk=event.pk)
    with scope(event=event):
        assert event.feature_flags['show_schedule'] is True
        assert event.settings.talk_schedule_public is True

    assert len(applied_tasks) == 0
