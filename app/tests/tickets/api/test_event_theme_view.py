from unittest import mock

from rest_framework.test import APIRequestFactory

from eventyay.api.views.event import EventThemeView


def test_event_theme_view_handles_missing_theme_key():
    request = APIRequestFactory().get("/api/v1/events/123/theme/")
    serializer_instance = mock.Mock()
    serializer_instance.data = {"config": {}}

    with (
        mock.patch("eventyay.api.views.event.get_object_or_404", return_value=object()),
        mock.patch("eventyay.api.views.event.RoomsEventSerializer", return_value=serializer_instance),
    ):
        response = EventThemeView.as_view()(request, event_id=123)

    assert response.status_code == 503
    assert response.data == "error happened when trying to get theme data of event: 123"
