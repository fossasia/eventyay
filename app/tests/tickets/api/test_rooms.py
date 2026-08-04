import pytest


@pytest.mark.django_db
def test_export_broadcast_configuration_invalid_format(token_client, organizer, event):
    resp = token_client.get(
        f"/api/v1/organizers/{organizer.slug}/events/{event.slug}/rooms/export-broadcast-configuration/",
        data={"_format": "invalid"},
    )

    assert resp.status_code == 400
    assert resp.data == {"_format": ["Invalid export format."]}
