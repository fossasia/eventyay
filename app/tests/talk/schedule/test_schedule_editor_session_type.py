import pytest
from django_scopes import scope

from eventyay.base.models import SubmissionType
from eventyay.orga.views.schedule import serialize_slot


class TestShowSessionTypeInScheduleEditor:
    @pytest.mark.django_db
    def test_serialize_slot_includes_session_type(self, event, slot):
        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name="Keynote Talk")
            slot.submission.submission_type = sub_type
            slot.submission.save()

            slot_data = serialize_slot(slot)
            assert slot_data["session_type"] == "Keynote Talk"
            assert slot_data["submission_type"] == "Keynote Talk"

    @pytest.mark.django_db
    def test_serialize_slot_break_session_type(self, event, break_slot):
        with scope(event=event):
            slot_data = serialize_slot(break_slot)
            assert slot_data.get("session_type") in (None, "")
            assert slot_data.get("submission_type") in (None, "")
