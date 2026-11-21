import datetime as dt
import json
import re

import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from eventyay.agenda.permissions import (
    is_submission_visible_via_accepted as agenda_submission_visible_via_accepted,
)
from eventyay.base.models import SpeakerProfile, Submission, SubmissionFavourite, SubmissionType, TalkSlot
from eventyay.talk_rules.agenda import is_submission_visible_via_accepted
from eventyay.talk_rules.submission import schedule_widget_featured_cache_key_part


def _inline_schedule_payload(html):
    match = re.search(
        r'<script id="pretalx-schedule-data" type="application/json">(.*?)</script>',
        html,
    )
    assert match, 'interactive schedule should embed its data'
    return json.loads(match.group(1))


def _enable_private_talk_testmode(event):
    event.private_testmode = True
    event.settings.private_testmode_talks = True
    event.save()


class TestShowAcceptedPubliclyToggle:
    @pytest.mark.django_db
    def test_toggle_view_get_method_not_allowed(self, orga_client, event):
        url = reverse("orga:schedule.toggle_accepted", kwargs={
            "organizer": event.organizer.slug,
            "event": event.slug,
        })
        response = orga_client.get(url)
        assert response.status_code == 405

    @pytest.mark.django_db
    def test_toggle_view_permission_required(self, client, event):
        url = reverse("orga:schedule.toggle_accepted", kwargs={
            "organizer": event.organizer.slug,
            "event": event.slug,
        })
        response = client.post(url, follow=False)
        assert response.status_code in (302, 403, 404)

    @pytest.mark.django_db
    def test_toggle_flips_feature_flag(self, orga_client, event):
        url = reverse("orga:schedule.toggle_accepted", kwargs={
            "organizer": event.organizer.slug,
            "event": event.slug,
        })
        assert not event.get_feature_flag("show_accepted_publicly")

        # Toggle on
        response = orga_client.post(url, follow=True)
        assert response.status_code == 200
        event.refresh_from_db()
        assert event.get_feature_flag("show_accepted_publicly") is True

        # Toggle off
        response = orga_client.post(url, follow=True)
        assert response.status_code == 200
        event.refresh_from_db()
        assert event.get_feature_flag("show_accepted_publicly") is False

    @pytest.mark.django_db
    def test_schedule_editor_renders_toggle_action(self, orga_client, event):
        url = reverse("orga:schedule.main", kwargs={
            "organizer": event.organizer.slug,
            "event": event.slug,
        })
        # Initially disabled: shows "Show Accepted Publicly"
        response = orga_client.get(url)
        assert response.status_code == 200
        assert "Show Accepted Publicly" in response.content.decode()

        # Turn on
        event.feature_flags["show_accepted_publicly"] = True
        event.save()

        # Enabled: shows "Hide accepted publicly"
        response = orga_client.get(url)
        assert response.status_code == 200
        assert "Hide accepted publicly" in response.content.decode()

    @pytest.mark.django_db
    def test_cache_key_reflects_toggle_state(self, event):
        with scope(event=event):
            event.feature_flags["show_accepted_publicly"] = False
            key_disabled = schedule_widget_featured_cache_key_part(event)
            assert "acc=0" in key_disabled

            event.feature_flags["show_accepted_publicly"] = True
            key_enabled = schedule_widget_featured_cache_key_part(event)
            assert "acc=1" in key_enabled
            assert key_disabled != key_enabled


class TestShowAcceptedPubliclyVisibility:
    @pytest.mark.django_db
    def test_build_data_includes_unscheduled_accepted_sessions(self, event, user):
        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name="Panel")

            accepted_sub = Submission.objects.create(
                title="Accepted Unscheduled Panel",
                event=event,
                submission_type=sub_type,
                abstract="Accepted abstract",
                content_locale="en",
            )
            accepted_sub.speakers.add(user)
            accepted_sub.accept()

            confirmed_sub = Submission.objects.create(
                title="Confirmed Unscheduled Talk",
                event=event,
                submission_type=sub_type,
                abstract="Confirmed abstract",
                content_locale="en",
            )
            confirmed_sub.speakers.add(user)
            confirmed_sub.accept()
            confirmed_sub.confirm()

            submitted_sub = Submission.objects.create(
                title="Pending Proposal",
                event=event,
                submission_type=sub_type,
                abstract="Pending abstract",
                content_locale="en",
            )
            submitted_sub.speakers.add(user)

            rejected_sub = Submission.objects.create(
                title="Rejected Proposal",
                event=event,
                submission_type=sub_type,
                abstract="Rejected abstract",
                content_locale="en",
            )
            rejected_sub.speakers.add(user)
            rejected_sub.reject()

            schedule = event.wip_schedule

            # 1. When toggle is disabled, unscheduled accepted talks are NOT included
            event.feature_flags["show_accepted_publicly"] = False
            event.save()
            data = schedule.build_data(respect_public_visibility=True)
            talk_codes = {t["code"] for t in data["talks"] if t.get("code")}
            assert accepted_sub.code not in talk_codes
            assert confirmed_sub.code not in talk_codes
            assert submitted_sub.code not in talk_codes
            assert rejected_sub.code not in talk_codes

            # 2. When toggle is enabled: accepted and confirmed are included, non-accepted are NOT
            event.feature_flags["show_accepted_publicly"] = True
            event.save()
            data = schedule.build_data(respect_public_visibility=True)
            talk_by_code = {t["code"]: t for t in data["talks"] if t.get("code")}

            assert accepted_sub.code in talk_by_code
            assert confirmed_sub.code in talk_by_code
            assert submitted_sub.code not in talk_by_code
            assert rejected_sub.code not in talk_by_code

            # Verify unscheduled sessions must NOT have invented times or rooms
            accepted_talk = talk_by_code[accepted_sub.code]
            assert accepted_talk["start"] is None
            assert accepted_talk["end"] is None
            assert accepted_talk["room"] is None
            assert accepted_talk["schedule_pending"] is True
            assert accepted_talk["title"] == "Accepted Unscheduled Panel"

            confirmed_talk = talk_by_code[confirmed_sub.code]
            assert confirmed_talk["start"] is None
            assert confirmed_talk["end"] is None
            assert confirmed_talk["room"] is None
            assert confirmed_talk["schedule_pending"] is True

            # 3. When private_testmode_talks_enabled is True, accepted talks are excluded from public build_data
            event.private_testmode = True
            event.settings.private_testmode_talks = True
            event.save()
            data = schedule.build_data(respect_public_visibility=True)
            talk_codes = {t["code"] for t in data["talks"] if t.get("code")}
            assert accepted_sub.code not in talk_codes
            assert confirmed_sub.code not in talk_codes

    @pytest.mark.django_db
    def test_public_talk_page_visibility_respects_toggle(self, client, event, user):
        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name="Talk")

            sub = Submission.objects.create(
                title="Public Accepted Talk",
                event=event,
                submission_type=sub_type,
                abstract="Abstract",
                content_locale="en",
            )
            sub.speakers.add(user)
            sub.accept()

            # Schedule is unpublished
            event.talks_published = False
            event.feature_flags["show_schedule"] = False
            event.feature_flags["show_accepted_publicly"] = False
            event.save()

            talk_url = sub.urls.public

        # 1. When show_accepted_publicly is False, anonymous visitor gets 404
        response = client.get(talk_url)
        assert response.status_code == 404

        # 2. When show_accepted_publicly is True, anonymous visitor gets 200
        event.feature_flags["show_accepted_publicly"] = True
        event.save()

        response = client.get(talk_url)
        assert response.status_code == 200
        assert "Public Accepted Talk" in response.content.decode()

        # 3. If private_testmode_talks_enabled is True, anonymous visitor gets 404 even with show_accepted_publicly=True
        event.private_testmode = True
        event.settings.private_testmode_talks = True
        event.save()

        response = client.get(talk_url)
        assert response.status_code == 404

        # 4. If submission is rejected, even with show_accepted_publicly=True it should return 404
        event.private_testmode = False
        event.settings.private_testmode_talks = False
        event.save()
        with scope(event=event):
            sub.reject()
        response = client.get(talk_url)
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_is_submission_visible_via_accepted_private_testmode(self, event, confirmed_submission):
        with scope(event=event):
            event.feature_flags["show_accepted_publicly"] = True
            event.private_testmode = False
            event.settings.private_testmode_talks = False
            event.save()
            assert is_submission_visible_via_accepted(None, confirmed_submission) is True
            assert agenda_submission_visible_via_accepted(None, confirmed_submission) is True

            event.private_testmode = True
            event.settings.private_testmode_talks = True
            event.save()
            assert is_submission_visible_via_accepted(None, confirmed_submission) is False
            assert agenda_submission_visible_via_accepted(None, confirmed_submission) is False

    @pytest.mark.django_db
    def test_build_data_compact_pending_submissions_only_on_default_day(self, event, slot, user):
        import datetime as dt

        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name="Keynote")
            pending_sub = Submission.objects.create(
                title="Unscheduled Keynote",
                event=event,
                submission_type=sub_type,
                abstract="Abstract",
                content_locale="en",
            )
            pending_sub.speakers.add(user)
            pending_sub.accept()

            event.feature_flags["show_accepted_publicly"] = True
            event.save()

            schedule = event.wip_schedule
            index_data = schedule.build_data(compact=True, index_only=True, respect_public_visibility=True)
            assert len(index_data["talks"]) == 0

            days = index_data["days"]
            assert len(days) >= 1
            default_day_str = days[0]
            default_day = dt.date.fromisoformat(default_day_str)
            other_day = default_day + dt.timedelta(days=1)

            # Requesting default day: pending session is included
            data_default = schedule.build_data(compact=True, on_date=default_day, respect_public_visibility=True)
            codes_default = {t["code"] for t in data_default["talks"] if t.get("code")}
            assert pending_sub.code in codes_default

            # Requesting other day: pending session is excluded
            data_other = schedule.build_data(compact=True, on_date=other_day, respect_public_visibility=True)
            codes_other = {t["code"] for t in data_other["talks"] if t.get("code")}
            assert pending_sub.code not in codes_other

    @pytest.mark.django_db
    def test_filter_updated_includes_newly_accepted_submission(self, event, user):
        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name="Talk")
            sub = Submission.objects.create(
                title="Just Accepted",
                event=event,
                submission_type=sub_type,
                abstract="Abstract",
                content_locale="en",
            )
            sub.speakers.add(user)
            stale = now() - dt.timedelta(days=2)
            Submission.objects.filter(pk=sub.pk).update(updated=stale)
            cutoff = now() - dt.timedelta(hours=1)
            sub.accept()
            sub.refresh_from_db()
            assert sub.updated >= cutoff

            event.feature_flags["show_accepted_publicly"] = True
            event.save()
            data = event.wip_schedule.build_data(
                respect_public_visibility=True,
                filter_updated=cutoff,
            )
            codes = {talk["code"] for talk in data["talks"] if talk.get("code")}
            assert sub.code in codes

    @pytest.mark.django_db
    def test_public_unreleased_schedule_hides_private_grid_entries(self, client, rf, event, user, room):
        from django.contrib.auth.models import AnonymousUser

        from eventyay.agenda.views.utils import build_schedule_json

        request = rf.get('/schedule/')
        request.user = AnonymousUser()
        request.event = event
        with scope(event=event):
            event.talks_published = False
            event.feature_flags['show_schedule'] = False
            event.feature_flags['show_accepted_publicly'] = True
            event.save()
            sub_type = SubmissionType.objects.create(event=event, name='Talk')
            accepted = Submission.objects.create(
                title='Public Accepted Talk',
                event=event,
                submission_type=sub_type,
                abstract='Abstract',
                content_locale='en',
            )
            accepted.speakers.add(user)
            accepted.accept()
            slot = event.wip_schedule.talks.get(submission=accepted)
            slot.room = room
            slot.start = event.datetime_from
            slot.end = event.datetime_from + dt.timedelta(minutes=30)
            slot.save()
            TalkSlot.objects.create(
                schedule=event.wip_schedule,
                room=room,
                description='Secret Break',
                start=event.datetime_from + dt.timedelta(hours=1),
                end=event.datetime_from + dt.timedelta(hours=1, minutes=15),
            )
            schedule = event.wip_schedule

        with scope(event=event):
            public = json.loads(
                build_schedule_json(
                    request,
                    schedule,
                    compact=False,
                    respect_public_visibility=True,
                    include_scheduled_slots=True,
                )
            )
        public_talks = {item.get('code'): item for item in public['talks'] if item.get('code')}
        assert accepted.code in public_talks
        assert public_talks[accepted.code]['room'] == room.pk
        assert public_talks[accepted.code]['state'] is None
        assert 'Secret Break' not in json.dumps(public)

        with scope(event=event):
            preview = json.loads(
                build_schedule_json(
                    request,
                    schedule,
                    compact=False,
                    respect_public_visibility=False,
                    include_scheduled_slots=True,
                )
            )
        assert 'Secret Break' in json.dumps(preview)

        widget = client.get(event.urls.schedule + 'widgets/schedule.json')
        assert widget.status_code == 200
        assert 'Secret Break' not in widget.content.decode()
        widget_talk = next(item for item in widget.json()['talks'] if item.get('code') == accepted.code)
        assert widget_talk['room'] == room.pk
        assert widget_talk['state'] is None

    @pytest.mark.django_db
    def test_pending_cards_include_favourite_counts(self, event, user):
        with scope(event=event):
            event.feature_flags['show_accepted_publicly'] = True
            event.feature_flags['session_popularity_enabled'] = True
            event.save()
            sub_type = SubmissionType.objects.create(event=event, name='Talk')
            accepted = Submission.objects.create(
                title='Favourited Pending Talk',
                event=event,
                submission_type=sub_type,
                abstract='Abstract',
                content_locale='en',
            )
            accepted.speakers.add(user)
            accepted.accept()
            SubmissionFavourite.objects.create(user=user, submission=accepted)
            data = event.wip_schedule.build_data(
                respect_public_visibility=True,
                include_scheduled_slots=False,
            )
        talk = next(item for item in data['talks'] if item.get('code') == accepted.code)
        assert talk['schedule_pending'] is True
        assert talk['fav_count'] == 1

    @pytest.mark.django_db
    def test_public_wip_schedule_json_refreshes_when_acceptance_changes(
        self, rf, event, user, django_capture_on_commit_callbacks
    ):
        from django.contrib.auth.models import AnonymousUser

        from eventyay.agenda.views.utils import build_schedule_json

        request = rf.get('/schedule/')
        request.user = AnonymousUser()
        request.event = event
        with scope(event=event):
            event.feature_flags['show_accepted_publicly'] = True
            event.save()
            sub_type = SubmissionType.objects.create(event=event, name='Talk')
            first = Submission.objects.create(
                title='First Accepted',
                event=event,
                submission_type=sub_type,
                abstract='Abstract',
                content_locale='en',
            )
            first.speakers.add(user)
            with django_capture_on_commit_callbacks(execute=True):
                first.accept()
            schedule = event.wip_schedule

        with scope(event=event):
            cached = build_schedule_json(request, schedule, compact=False, respect_public_visibility=True)
        assert first.code in cached

        with scope(event=event):
            second = Submission.objects.create(
                title='Second Accepted',
                event=event,
                submission_type=sub_type,
                abstract='Abstract',
                content_locale='en',
            )
            second.speakers.add(user)
            with django_capture_on_commit_callbacks(execute=True):
                second.accept()
            refreshed = build_schedule_json(request, schedule, compact=False, respect_public_visibility=True)
        assert second.code in refreshed

        with scope(event=event):
            with django_capture_on_commit_callbacks(execute=True):
                second.reject()
            after_reject = build_schedule_json(request, schedule, compact=False, respect_public_visibility=True)
        assert second.code not in after_reject
        assert first.code in after_reject

    @pytest.mark.django_db
    def test_toggle_normalizes_legacy_flag_list(self, orga_client, event):
        event.feature_flags = ["show_schedule"]
        event.save(update_fields=["feature_flags"])
        url = reverse("orga:schedule.toggle_accepted", kwargs={
            "organizer": event.organizer.slug,
            "event": event.slug,
        })
        response = orga_client.post(url, follow=True)
        assert response.status_code == 200
        event.refresh_from_db()
        assert event.get_feature_flag("show_accepted_publicly") is True
        assert isinstance(event.feature_flags, dict)

    @pytest.mark.django_db
    def test_reviewer_cannot_toggle(self, review_client, event):
        url = reverse("orga:schedule.toggle_accepted", kwargs={
            "organizer": event.organizer.slug,
            "event": event.slug,
        })
        response = review_client.post(url)
        assert response.status_code == 404
        event.refresh_from_db()
        assert event.get_feature_flag("show_accepted_publicly") is False


class TestShowAcceptedPubliclyEndToEnd:
    @pytest.mark.django_db
    def test_public_schedule_shows_pending_sessions_without_a_release(self, client, event, user, room):
        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name="Talk")
            accepted = Submission.objects.create(
                title="Accepted Coming Soon",
                event=event,
                submission_type=sub_type,
                abstract="Abstract",
                content_locale="en",
            )
            accepted.speakers.add(user)
            accepted.accept()
            rejected = Submission.objects.create(
                title="Hidden Rejected Talk",
                event=event,
                submission_type=sub_type,
                abstract="Nope",
                content_locale="en",
            )
            rejected.speakers.add(user)
            rejected.reject()
            withdrawn = Submission.objects.create(
                title="Hidden Withdrawn Talk",
                event=event,
                submission_type=sub_type,
                abstract="Gone",
                content_locale="en",
            )
            withdrawn.speakers.add(user)
            withdrawn.accept()
            withdrawn.withdraw()

            unplaced = Submission.objects.create(
                title="Accepted Not Placed",
                event=event,
                submission_type=sub_type,
                abstract="Later",
                content_locale="en",
            )
            unplaced.speakers.add(user)
            unplaced.accept()

            confirmed = Submission.objects.create(
                title="Confirmed On The Grid",
                event=event,
                submission_type=sub_type,
                abstract="Ready",
                content_locale="en",
            )
            confirmed.speakers.add(user)
            confirmed.accept()
            confirmed.confirm()

            # Placed on the working schedule before any release, without forcing visibility.
            slot = event.wip_schedule.talks.get(submission=accepted)
            slot.room = room
            slot.start = event.datetime_from
            slot.end = event.datetime_from + dt.timedelta(minutes=30)
            slot.save()
            confirmed_slot = event.wip_schedule.talks.get(submission=confirmed)
            confirmed_slot.room = room
            confirmed_slot.start = event.datetime_from + dt.timedelta(hours=1)
            confirmed_slot.end = event.datetime_from + dt.timedelta(hours=1, minutes=30)
            confirmed_slot.save()

            event.talks_published = False
            event.feature_flags["show_schedule"] = False
            event.feature_flags["show_accepted_publicly"] = False
            event.save()
            SpeakerProfile.objects.get_or_create(event=event, user=user)
            profile = user.profiles.get(event=event)

        assert client.get(event.urls.schedule, HTTP_ACCEPT="text/html").status_code == 404
        assert client.get(event.urls.talks).status_code == 404

        event.feature_flags["show_accepted_publicly"] = True
        event.save()

        page = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
        assert page.status_code == 200
        assert "Accepted Coming Soon" in page.content.decode()
        assert "Confirmed On The Grid" in page.content.decode()
        assert "Hidden Rejected Talk" not in page.content.decode()
        assert "Hidden Withdrawn Talk" not in page.content.decode()
        payload = _inline_schedule_payload(page.text)
        talk = next(item for item in payload["talks"] if item.get("code") == accepted.code)
        assert talk["start"] is not None
        assert talk["end"] is not None
        assert talk["room"] == room.pk
        assert talk.get("schedule_pending") is not True
        assert str(room.name) in page.text
        confirmed_talk = next(item for item in payload["talks"] if item.get("code") == confirmed.code)
        assert confirmed_talk["start"] is not None
        assert confirmed_talk["end"] is not None
        assert confirmed_talk["room"] == room.pk
        assert confirmed_talk.get("schedule_pending") is not True
        pending = next(item for item in payload["talks"] if item.get("code") == unplaced.code)
        assert pending["start"] is None
        assert pending["room"] is None
        assert pending["schedule_pending"] is True

        widget = client.get(event.urls.schedule + "widgets/schedule.json")
        assert widget.status_code == 200
        widget_talk = next(item for item in widget.json()["talks"] if item.get("code") == accepted.code)
        assert widget_talk["start"] is not None
        assert widget_talk["room"] == room.pk
        widget_pending = next(item for item in widget.json()["talks"] if item.get("code") == unplaced.code)
        assert widget_pending["start"] is None
        assert widget_pending["room"] is None

        # /sessions/ redirects to the schedule. The middleware must allow it
        # while talk pages are still unpublished.
        sessions = client.get(event.urls.talks, follow=True, HTTP_ACCEPT="text/html")
        assert sessions.redirect_chain
        assert sessions.redirect_chain[0][1] == 301
        assert sessions.status_code == 200
        assert "Accepted Coming Soon" in sessions.content.decode()

        talk_page = client.get(accepted.urls.public)
        assert talk_page.status_code == 200
        speaker_page = client.get(profile.urls.public)
        assert speaker_page.status_code == 200

        # The organiser preview stays closed. Plain text includes the placement.
        assert client.get(event.urls.schedule + "v/wip/", HTTP_ACCEPT="text/html").status_code == 404
        plain = client.get(event.urls.schedule + "?format=list", HTTP_ACCEPT="text/plain")
        plain_body = plain.content.decode()
        assert "Accepted Coming Soon" in plain_body
        assert str(room.name) in plain_body
        assert "Accepted Not Placed" not in plain_body
        assert "Hidden Rejected Talk" not in plain_body

        # Public talk test mode does not hide accepted sessions.
        event.settings.talks_testmode = True
        assert client.get(event.urls.schedule, HTTP_ACCEPT="text/html").status_code == 200

        # Private test mode for tickets only (talks left public) still shows them.
        event.private_testmode = True
        event.settings.private_testmode_tickets = True
        event.settings.private_testmode_talks = False
        event.save()
        assert client.get(event.urls.schedule, HTTP_ACCEPT="text/html").status_code == 200

        # Private talk test mode hides schedule, JSON, talk, speaker, and feedback.
        event.feature_flags["use_feedback"] = True
        event.save()
        _enable_private_talk_testmode(event)
        assert client.get(event.urls.schedule, HTTP_ACCEPT="text/html").status_code == 404
        assert client.get(event.urls.schedule + "widgets/schedule.json").status_code == 404
        assert client.get(accepted.urls.public).status_code == 404
        assert client.get(profile.urls.public).status_code == 404
        assert client.get(accepted.urls.feedback).status_code == 404

    @pytest.mark.django_db
    def test_released_schedule_hides_times_until_timetable_is_public(self, client, event, slot):
        with scope(event=event):
            event.talks_published = True
            event.feature_flags["show_schedule"] = False
            event.feature_flags["show_accepted_publicly"] = True
            event.save()
            code = slot.submission.code
            title = str(slot.submission.title)

        page = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
        assert page.status_code == 200
        payload = _inline_schedule_payload(page.text)
        talk = next(item for item in payload["talks"] if item.get("code") == code)
        assert talk["schedule_pending"] is True
        assert talk["start"] is None
        assert talk["room"] is None
        assert title in page.content.decode()
        assert str(slot.room.name) not in page.content.decode()

        event.feature_flags["show_widget_if_not_public"] = True
        event.save()
        hidden = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
        assert hidden.status_code == 200
        hidden_payload = _inline_schedule_payload(hidden.text)
        hidden_talk = next(item for item in hidden_payload["talks"] if item.get("code") == code)
        assert hidden_talk["start"] is None
        assert hidden_talk["room"] is None
        widget = client.get(event.urls.schedule + "widgets/schedule.json")
        assert widget.status_code == 200
        widget_talk = next(item for item in widget.json()["talks"] if item.get("code") == code)
        assert widget_talk["start"] is not None
        assert widget_talk["room"] == slot.room_id

        event.feature_flags["show_schedule"] = True
        event.save()
        published = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
        assert published.status_code == 200
        published_payload = _inline_schedule_payload(published.text)
        published_talk = next(item for item in published_payload["talks"] if item.get("code") == code)
        assert published_talk["start"] is not None
        assert published_talk["room"] == slot.room_id
        assert published_talk.get("schedule_pending") is not True


    @pytest.mark.django_db
    def test_release_after_show_accepted_publishes_placed_sessions(self, client, event, user, room):
        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name="Talk")
            placed = Submission.objects.create(
                title="Placed Then Released",
                event=event,
                submission_type=sub_type,
                abstract="Abstract",
                content_locale="en",
            )
            placed.speakers.add(user)
            placed.accept()
            unplaced = Submission.objects.create(
                title="Still Unplaced",
                event=event,
                submission_type=sub_type,
                abstract="Later",
                content_locale="en",
            )
            unplaced.speakers.add(user)
            unplaced.accept()
            slot = event.wip_schedule.talks.get(submission=placed)
            slot.room = room
            slot.start = event.datetime_from
            slot.end = event.datetime_from + dt.timedelta(minutes=45)
            slot.save()
            event.talks_published = False
            event.feature_flags["show_schedule"] = False
            event.feature_flags["show_accepted_publicly"] = True
            event.save()
            placed_code = placed.code
            unplaced_code = unplaced.code

        before = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
        assert before.status_code == 200
        before_payload = _inline_schedule_payload(before.text)
        before_placed = next(item for item in before_payload["talks"] if item.get("code") == placed_code)
        assert before_placed["room"] == room.pk
        assert before_placed["start"] is not None

        with scope(event=event):
            event.talks_published = True
            event.feature_flags["show_schedule"] = True
            event.save()
            event.release_schedule("public-1")
            released_slot = event.current_schedule.talks.get(submission__code=placed_code)
            # A later edit on the working copy must not replace the release.
            wip_slot = event.wip_schedule.talks.get(submission__code=placed_code)
            wip_slot.room = None
            wip_slot.start = None
            wip_slot.end = None
            wip_slot.save()

        published = client.get(event.urls.schedule, HTTP_ACCEPT="text/html")
        assert published.status_code == 200
        payload = _inline_schedule_payload(published.text)
        talk = next(item for item in payload["talks"] if item.get("code") == placed_code)
        assert talk["start"] is not None
        assert talk["room"] == released_slot.room_id
        assert str(room.name) in published.text
        pending = next(item for item in payload["talks"] if item.get("code") == unplaced_code)
        assert pending["start"] is None
        assert pending["room"] is None
        assert pending["schedule_pending"] is True


