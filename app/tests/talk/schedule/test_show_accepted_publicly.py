import pytest
from django.urls import reverse
from django_scopes import scope

from eventyay.agenda.permissions import is_submission_visible_via_accepted

from eventyay.base.models import Submission, SubmissionType
from eventyay.talk_rules.submission import schedule_widget_featured_cache_key_part


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

            event.private_testmode = True
            event.settings.private_testmode_talks = True
            event.save()
            assert is_submission_visible_via_accepted(None, confirmed_submission) is False

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


