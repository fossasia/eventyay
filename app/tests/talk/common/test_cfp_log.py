import pytest
from django_scopes import scope

from eventyay.base import signals as base_signals
from eventyay.base.models.log import ActivityLog, LogEntry
from eventyay.common import signals as common_signals
from eventyay.common.log_display import LOG_NAMES


@pytest.fixture
def activity_log(event, submission):
    return ActivityLog(
        event=event, content_object=submission, action_type="eventyay.submission.create"
    )


@pytest.mark.django_db
def test_activity_log_display(activity_log):
    assert activity_log.display == LOG_NAMES.get(activity_log.action_type)


@pytest.mark.django_db
def test_activity_log_display_incorrect(activity_log):
    activity_log.action_type = "foo"
    assert activity_log.display == "foo"


@pytest.mark.django_db
def test_log_urls(
    activity_log, submission, choice_question, answer, mail_template, mail
):
    with scope(event=submission.event):
        assert submission.orga_urls.base in activity_log.display_object

        activity_log.content_object = submission.event.cfp
        del activity_log.display_object
        assert submission.event.cfp.urls.text in activity_log.display_object

        activity_log.content_object = choice_question
        del activity_log.display_object
        assert choice_question.urls.base in activity_log.display_object

        activity_log.content_object = choice_question.options.first()
        del activity_log.display_object
        assert choice_question.urls.base in activity_log.display_object

        activity_log.content_object = answer
        del activity_log.display_object
        assert answer.submission.orga_urls.base in activity_log.display_object
        answer.submission = None
        del activity_log.display_object
        assert answer.question.urls.base in activity_log.display_object

        activity_log.content_object = mail_template
        del activity_log.display_object
        assert mail_template.urls.base in activity_log.display_object

        activity_log.content_object = mail
        del activity_log.display_object
        assert mail.urls.base in activity_log.display_object


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action_type",
    (
        "eventyay.submission.create",
        "eventyay.submission.speakers.add",
        "eventyay.mail.sent",
        "eventyay.schedule.release",
    ),
)
def test_log_entry_display_uses_talk_log_names(event, submission, action_type):
    """Talk actions are stored as LogEntry and must render their readable name, not the raw key."""
    with scope(event=event):
        log_entry = LogEntry(event=event, content_object=submission, action_type=action_type)
        assert log_entry.display() == LOG_NAMES[action_type]


@pytest.mark.django_db
def test_log_entry_display_unknown_action_falls_back_to_action_type(event, submission):
    """Unknown action types still fall back to the raw key."""
    with scope(event=event):
        log_entry = LogEntry(event=event, content_object=submission, action_type="foo.bar")
        assert log_entry.display() == "foo.bar"


@pytest.mark.django_db
def test_log_entry_display_keeps_ticketing_names(event):
    """Actions rendered by the ticketing log display keep their existing wording."""
    with scope(event=event):
        log_entry = LogEntry(
            event=event, content_object=event, action_type="eventyay.event.plugins.enabled"
        )
        assert str(log_entry.display()) == "A plugin has been enabled."


@pytest.mark.django_db
def test_log_entry_display_object_links_talk_objects(event, submission, room, schedule):
    """Talk objects get readable links instead of the model repr."""
    with scope(event=event):
        log_entry = LogEntry(event=event, content_object=submission, action_type="eventyay.submission.create")
        assert submission.orga_urls.base in log_entry.display_object

        log_entry = LogEntry(event=event, content_object=schedule, action_type="eventyay.schedule.release")
        assert schedule.urls.public in log_entry.display_object
        assert "Schedule(" not in log_entry.display_object

        log_entry = LogEntry(event=event, content_object=room, action_type="eventyay.room.create")
        assert room.urls.edit in log_entry.display_object


@pytest.mark.django_db
def test_talk_dashboard_activity_shows_readable_text(orga_client, orga_user, event, submission):
    """The Talks dashboard shows the readable message, not the action key."""
    with scope(event=event):
        submission.log_action("eventyay.submission.create", user=orga_user, orga=True)

    response = orga_client.get(event.orga_urls.base, follow=True)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Recent talk activity" in content
    assert str(LOG_NAMES["eventyay.submission.create"]) in content
    assert "eventyay.submission.create" not in content


@pytest.mark.django_db
def test_log_entry_display_maps_legacy_pretalx_action_types(event, submission):
    """Legacy pretalx.* action types render through their eventyay alias."""
    with scope(event=event):
        log_entry = LogEntry(event=event, content_object=submission, action_type="pretalx.submission.speakers.add")
        assert log_entry.display() == LOG_NAMES["eventyay.submission.speakers.add"]


@pytest.mark.django_db
def test_log_entry_display_formats_templated_talk_names(event):
    """Templated names are formatted with the logged data."""
    data = '{"name": "Old event", "slug": "old", "organiser": "Org"}'
    with scope(event=event):
        log_entry = LogEntry(event=event, content_object=event, action_type="eventyay.event.delete", data=data)
        assert log_entry.display() == "The event Old event (old) by Org was deleted."


@pytest.mark.django_db
def test_log_entry_display_templated_name_with_missing_data_falls_back(event):
    """Templated names with missing data fall back to the action key."""
    with scope(event=event):
        log_entry = LogEntry(event=event, content_object=event, action_type="eventyay.event.delete", data="{}")
        assert log_entry.display() == "eventyay.event.delete"


@pytest.mark.django_db
def test_log_entry_display_without_event(user):
    """Account-level entries without an event still get a readable name."""
    log_entry = LogEntry(event=None, content_object=user, action_type="eventyay.user.password.update")
    assert log_entry.display() == LOG_NAMES["eventyay.user.password.update"]


@pytest.mark.django_db
def test_log_entry_display_object_links_unreleased_schedule_to_editor(event):
    """An unreleased schedule links to the schedule editor."""
    with scope(event=event):
        wip_schedule = event.wip_schedule
        log_entry = LogEntry(event=event, content_object=wip_schedule, action_type="eventyay.schedule.update")
        assert event.orga_urls.schedule in log_entry.display_object
        assert "Work in progress" in log_entry.display_object


@pytest.mark.django_db
def test_log_entry_display_object_escapes_titles(event, submission):
    """User-provided titles are escaped in the object link."""
    with scope(event=event):
        submission.title = "<script>alert(1)</script>"
        log_entry = LogEntry(event=event, content_object=submission, action_type="eventyay.submission.create")
        assert "<script>" not in log_entry.display_object
        assert "&lt;script&gt;" in log_entry.display_object


@pytest.mark.django_db
def test_log_entry_display_object_without_content_object(event, submission):
    """A missing content object renders an empty reference."""
    with scope(event=event):
        log_entry = LogEntry(event=event, content_object=submission, action_type="eventyay.submission.create")
        log_entry.content_object = None
        assert log_entry.display_object == ""


@pytest.mark.django_db
def test_talk_dashboard_activity_badges(orga_client, orga_user, event, submission):
    """Proposal and schedule rows get matching badges and no model repr."""
    with scope(event=event):
        submission.log_action("eventyay.submission.create", user=orga_user, orga=True)
        event.release_schedule("1.0", user=orga_user)

    response = orga_client.get(event.orga_urls.base, follow=True)

    content = response.content.decode()
    assert "td-activity-badge type-session" in content
    assert "td-activity-badge type-schedule" in content
    assert "Schedule(" not in content


@pytest.mark.django_db
def test_log_entry_display_object_does_not_link_deleted_rooms(event, room):
    """Deleted rooms are named without a link, since their edit page no longer exists."""
    with scope(event=event):
        room.deleted = True
        log_entry = LogEntry(event=event, content_object=room, action_type="eventyay.room.delete")
        assert room.urls.edit not in log_entry.display_object
        assert str(room.name) in log_entry.display_object


def test_common_activitylog_signals_reach_both_log_models():
    """Receivers connected through eventyay.common.signals also render LogEntry and ActivityLog."""
    assert common_signals.activitylog_display is base_signals.activitylog_display
    assert common_signals.activitylog_object_link is base_signals.activitylog_object_link


@pytest.mark.django_db
def test_talk_dashboard_session_type_actions_are_not_proposals(orga_client, orga_user, event, submission):
    """Session type changes are not labelled as proposals on the dashboard."""
    with scope(event=event):
        submission.submission_type.log_action("eventyay.submission_type.update", user=orga_user, orga=True)

    response = orga_client.get(event.orga_urls.base, follow=True)

    content = response.content.decode()
    assert "Recent talk activity" in content
    assert str(LOG_NAMES["eventyay.submission_type.update"]) in content
    assert "td-activity-badge type-session" not in content


@pytest.mark.django_db
def test_log_entry_exposes_person_id_like_activity_log(event, submission, orga_user):
    """Receivers written for ActivityLog can read person_id from a LogEntry too."""
    with scope(event=event):
        log_entry = LogEntry(event=event, content_object=submission, action_type="eventyay.submission.create")
        log_entry.user = orga_user
        assert log_entry.person_id == orga_user.pk
