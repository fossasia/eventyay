import pytest
from django.urls import reverse

from eventyay.orga.forms.event import ScheduleHtmlExportForm


@pytest.mark.django_db
def test_schedule_html_export_form(event):
    """ScheduleHtmlExportForm saves to the correct JSON fields on the Event model."""
    form = ScheduleHtmlExportForm(
        data={
            "export_html_on_release": True,
            "html_export_url": "https://example.com/schedule/",
        },
        obj=event,
    )
    assert form.is_valid(), form.errors
    form.save()

    event.refresh_from_db()
    assert event.feature_flags["export_html_on_release"] is True
    assert event.display_settings["html_export_url"] == "https://example.com/schedule/"


@pytest.mark.django_db
def test_import_export_page_contains_schedule_html_export_tab(orga_client, event):
    """The Import/Export settings page renders the Schedule HTML export tab."""
    url = reverse(
        "orga:settings.import_export",
        kwargs={"organizer": event.organiser.slug, "event": event.slug},
    )
    response = orga_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Schedule HTML export" in content
    assert "schedule_html_export_form" in response.context


@pytest.mark.django_db
def test_import_export_settings_save_html_export(orga_client, event):
    """Posting save_schedule_html_export persists both fields to the event."""
    url = reverse(
        "orga:settings.import_export",
        kwargs={"organizer": event.organiser.slug, "event": event.slug},
    )
    response = orga_client.post(
        url,
        data={
            "action": "save_schedule_html_export",
            "export_html_on_release": "on",
            "html_export_url": "https://schedule.example.org/export/",
        },
        follow=True,
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.feature_flags.get("export_html_on_release") is True
    assert event.display_settings.get("html_export_url") == "https://schedule.example.org/export/"


@pytest.mark.django_db
def test_import_export_settings_save_invalid_url(orga_client, event):
    """An invalid HTML export URL returns 400 and reports the field error."""
    url = reverse(
        "orga:settings.import_export",
        kwargs={"organizer": event.organiser.slug, "event": event.slug},
    )
    response = orga_client.post(
        url,
        data={
            "action": "save_schedule_html_export",
            "export_html_on_release": "on",
            "html_export_url": "not-a-valid-url",
        },
    )
    assert response.status_code == 400
    assert "schedule_html_export_form" in response.context
    assert "html_export_url" in response.context["schedule_html_export_form"].errors


@pytest.mark.django_db
def test_import_export_settings_html_export_fields_not_in_general_settings(orga_client, event):
    """The HTML export fields must not appear in the general Talk settings tab."""
    url = reverse(
        "orga:settings.event.view",
        kwargs={"organizer": event.organiser.slug, "event": event.slug},
    )
    response = orga_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "export_html_on_release" not in content
    assert "html_export_url" not in content


@pytest.mark.django_db
def test_import_submissions_missing_file(event, orga_user):
    """Calling import_submissions with a nonexistent CachedFile raises ImportExecutionError."""
    from eventyay.base.services.talkimport import import_submissions, ImportExecutionError

    with pytest.raises(ImportExecutionError) as exc_info:
        import_submissions(
            event=event.pk,
            fileid="00000000-0000-0000-0000-000000000000",
            settings={},
            locale="en",
            user_id=orga_user.pk,
        )
    assert "session file could not be found" in str(exc_info.value)

