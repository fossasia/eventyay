import pytest
from django_scopes import scope

from eventyay.base.models import Event


@pytest.mark.django_db
def test_toggle_schedule_visibility_saves_locally_without_sync_task(organizer_client, event, team, monkeypatch):
    applied_tasks = []
    monkeypatch.setattr(
        'celery.app.task.Task.apply_async',
        lambda *args, **kwargs: applied_tasks.append((args, kwargs)),
    )

    team.can_change_submissions = True
    team.save(update_fields=['can_change_submissions'])

    with scope(event=event):
        assert event.get_feature_flag('show_schedule') is True

    response = organizer_client.post(event.orga_urls.toggle_schedule, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    with scope(event=event):
        assert event.feature_flags['show_schedule'] is False
        assert event.settings.talk_schedule_public is False

    response = organizer_client.post(event.orga_urls.toggle_schedule, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    with scope(event=event):
        assert event.feature_flags['show_schedule'] is True
        assert event.settings.talk_schedule_public is True

    assert len(applied_tasks) == 0
