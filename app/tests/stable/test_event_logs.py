import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client, override_settings
from django.urls import reverse
from django_scopes import scope, scopes_disabled

from eventyay.api.models import OAuthApplication
from eventyay.base.models import LogEntry
from eventyay.base.models.auth import StaffSession
from eventyay.base.models.devices import Device
from eventyay.base.models.organizer import TeamAPIToken


@pytest.mark.django_db
@override_settings(SITE_URL="https://testserver")
def test_event_logs_search_filters_results(
    organizer_client, staff_user, organizer, event, user
):
    content_type = ContentType.objects.get_for_model(event)

    with scope(event=event):
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


@pytest.mark.django_db
@override_settings(SITE_URL="https://testserver")
def test_event_logs_search_related_names_and_combined_filters(
    organizer_client, organizer, event, user, team
):
    content_type = ContentType.objects.get_for_model(event)

    with scopes_disabled():
        device = Device.objects.create(
            organizer=organizer,
            all_events=True,
            name="Searchable Test Device",
        )

    api_token = TeamAPIToken.objects.create(
        team=team,
        name="Searchable Test API Token",
    )
    oauth_application = OAuthApplication.objects.create(
        name="Searchable Test OAuth App",
        redirect_uris="https://example.com/callback",
        client_type="confidential",
        authorization_grant_type="authorization-code",
    )

    with scope(event=event):
        device_log = LogEntry.objects.create(
            event=event,
            content_type=content_type,
            object_id=event.pk,
            user=user,
            device=device,
            action_type="test.device.search",
        )
        api_token_log = LogEntry.objects.create(
            event=event,
            content_type=content_type,
            object_id=event.pk,
            user=user,
            api_token=api_token,
            action_type="test.api_token.search",
        )
        oauth_application_log = LogEntry.objects.create(
            event=event,
            content_type=content_type,
            object_id=event.pk,
            user=user,
            oauth_application=oauth_application,
            action_type="test.oauth_application.search",
        )
        combined_user_log = LogEntry.objects.create(
            event=event,
            content_type=content_type,
            object_id=event.pk,
            user=user,
            action_type="test.combined-filter-marker",
        )
        LogEntry.objects.create(
            event=event,
            content_type=content_type,
            object_id=event.pk,
            user=None,
            action_type="test.combined-filter-marker",
        )

    url = reverse(
        "control:event.log",
        kwargs={"organizer": organizer.slug, "event": event.slug},
    )

    for query, expected_log in (
        (device.name, device_log),
        (api_token.name, api_token_log),
        (oauth_application.name, oauth_application_log),
    ):
        response = organizer_client.get(url, {"q": query})
        assert response.status_code == 200
        assert list(response.context["logs"]) == [expected_log]

    response = organizer_client.get(
        url,
        {"q": "combined-filter-marker", "user": "yes"},
    )
    assert response.status_code == 200
    assert list(response.context["logs"]) == [combined_user_log]
