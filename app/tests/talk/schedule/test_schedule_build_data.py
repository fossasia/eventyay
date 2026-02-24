import pytest
from django_scopes import scope

from pretalx.submission.models import Answer, Question, QuestionVariant


@pytest.fixture
def public_question(event):
    with scope(event=event):
        return Question.objects.create(
            event=event,
            question="Favourite colour?",
            variant=QuestionVariant.STRING,
            target="submission",
            is_public=True,
            position=0,
        )


@pytest.fixture
def private_question(event):
    with scope(event=event):
        return Question.objects.create(
            event=event,
            question="Secret preference?",
            variant=QuestionVariant.STRING,
            target="submission",
            is_public=False,
            position=1,
        )


@pytest.mark.django_db
def test_build_data_basic_structure(event, slot):
    """build_data returns top-level keys for schedule payload."""
    with scope(event=event):
        data = slot.schedule.build_data()
        for key in ("talks", "version", "timezone", "event_start", "event_end", "tracks", "rooms", "speakers"):
            assert key in data, f"Missing key: {key}"
        assert isinstance(data["talks"], list)
        assert len(data["talks"]) >= 1


@pytest.mark.django_db
def test_build_data_talk_base_fields(event, slot):
    """Each talk dict has the expected base fields."""
    with scope(event=event):
        data = slot.schedule.build_data()
        talk = next(t for t in data["talks"] if t.get("code"))
        expected_keys = {
            "code", "id", "title", "abstract", "description",
            "speakers", "track", "start", "end", "room",
            "duration", "updated", "fav_count", "tags", "session_type",
        }
        assert expected_keys.issubset(talk.keys())


@pytest.mark.django_db
def test_build_data_no_enrich_omits_extra_fields(event, slot):
    """Without enrich=True, talks lack resources/answers/exporters/recording_iframe."""
    with scope(event=event):
        data = slot.schedule.build_data(enrich=False)
        talk = next(t for t in data["talks"] if t.get("code"))
        for key in ("resources", "answers", "exporters", "recording_iframe"):
            assert key not in talk, f"Unexpected enriched key without enrich=True: {key}"


@pytest.mark.django_db
def test_build_data_enrich_adds_extra_fields(event, slot):
    """enrich=True adds resources, answers, exporters, recording_iframe."""
    with scope(event=event):
        data = slot.schedule.build_data(enrich=True)
        talk = next(t for t in data["talks"] if t.get("code"))
        for key in ("resources", "answers", "exporters", "recording_iframe"):
            assert key in talk, f"Missing enriched key: {key}"


@pytest.mark.django_db
def test_build_data_enrich_resources(event, slot, confirmed_resource):
    """Enriched talk includes attached resources."""
    with scope(event=event):
        data = slot.schedule.build_data(enrich=True)
        talk = next(t for t in data["talks"] if t.get("code"))
        assert len(talk["resources"]) >= 1
        res = talk["resources"][0]
        assert "description" in res
        assert "resource" in res


@pytest.mark.django_db
def test_build_data_enrich_answers_public_only(
    event, slot, public_question, private_question
):
    """Only answers to public questions appear in enriched data."""
    sub = slot.submission
    with scope(event=event):
        Answer.objects.create(answer="Blue", submission=sub, question=public_question)
        Answer.objects.create(answer="Hidden", submission=sub, question=private_question)
        data = slot.schedule.build_data(enrich=True)
        talk = next(t for t in data["talks"] if t["code"] == sub.code)
        questions = [a["question"] for a in talk["answers"]]
        assert str(public_question.question) in questions
        assert str(private_question.question) not in questions


@pytest.mark.django_db
def test_build_data_enrich_exporters(event, slot):
    """Enriched talk includes per-talk export URLs for all formats."""
    with scope(event=event):
        data = slot.schedule.build_data(enrich=True)
        talk = next(t for t in data["talks"] if t.get("code"))
        exp = talk["exporters"]
        for fmt in ("ics", "json", "xml", "xcal", "google_calendar", "webcal"):
            assert fmt in exp, f"Missing exporter: {fmt}"
            assert talk["code"] in exp[fmt]


@pytest.mark.django_db
def test_build_data_enrich_recording_iframe_empty(event, slot):
    """Without a recording provider, recording_iframe is empty string."""
    with scope(event=event):
        data = slot.schedule.build_data(enrich=True)
        talk = next(t for t in data["talks"] if t.get("code"))
        assert talk["recording_iframe"] == ""


@pytest.mark.django_db
def test_build_data_break_slot(event, break_slot):
    """Break slots produce minimal dicts without code/speakers."""
    with scope(event=event):
        data = break_slot.schedule.build_data()
        breaks = [t for t in data["talks"] if not t.get("code")]
        assert len(breaks) >= 1
        brk = breaks[0]
        assert "id" in brk
        assert "title" in brk
        assert "start" in brk
        assert "end" in brk
        assert "speakers" not in brk


@pytest.mark.django_db
def test_build_data_rooms_from_talks_only(event, slot):
    """When all_rooms=False, only rooms used by talks appear."""
    with scope(event=event):
        data = slot.schedule.build_data(all_rooms=False)
        room_ids = {r["id"] for r in data["rooms"]}
        assert slot.room_id in room_ids


@pytest.mark.django_db
def test_build_data_speakers(event, slot):
    """Speakers referenced by talks appear in the speakers list."""
    with scope(event=event):
        data = slot.schedule.build_data()
        talk = next(t for t in data["talks"] if t.get("code"))
        speaker_codes_in_talks = set(talk["speakers"])
        speaker_codes_in_list = {s["code"] for s in data["speakers"]}
        assert speaker_codes_in_talks.issubset(speaker_codes_in_list)
        for s in data["speakers"]:
            assert "code" in s
            assert "name" in s
