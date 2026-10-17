import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client, override_settings
from django.urls import reverse

from eventyay.base.models import LogEntry
from eventyay.base.models.auth import StaffSession


@pytest.mark.django_db
@override_settings(SITE_URL="https://testserver")
def test_event_logs_search_filters_results(
    organizer_client, staff_user, organizer, event, user
):
    content_type = ContentType.objects.get_for_model(event)

    matching_log = LogEntry.objects.create(
        event=event,
        content_type=content_type,
        object_id=event.pk,
        user=user,
        action_type="test.search.match",
        data='{"message": "unique needle"}',
    )
    other_log = LogEntry.objects.create(
        event=event,
        content_type=content_type,
        object_id=event.pk,
        user=user,
        action_type="test.search.other",
        data='{"message": "different entry"}',
    )

    url = reverse(
        "control:event.log",
        kwargs={"organizer": organizer.slug, "event": event.slug},
    )

    response = organizer_client.get(url, {"q": "needle"})
    assert response.status_code == 200
    assert list(response.context["logs"]) == []

    response = organizer_client.get(url, {"q": "TEST.SEARCH.MATCH"})
    assert response.status_code == 200
    assert list(response.context["logs"]) == [matching_log]

    response = organizer_client.get(url, {"q": user.email})
    assert response.status_code == 200
    assert matching_log in list(response.context["logs"])
    assert other_log in list(response.context["logs"])

    response = organizer_client.get(url, {"q": ""})
    assert response.status_code == 200
    assert set(response.context["logs"]) == {matching_log, other_log}

    staff_client = Client()
    staff_client.force_login(staff_user)
    session_key = staff_client.session.session_key
    StaffSession.objects.create(user=staff_user, session_key=session_key)

    response = staff_client.get(url, {"q": "needle"})
    assert response.status_code == 200
    assert list(response.context["logs"]) == [matching_log]
