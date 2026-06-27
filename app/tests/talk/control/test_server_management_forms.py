import pytest

from eventyay.control.forms.server_management import EventForm


@pytest.mark.django_db
def test_event_form_stores_feature_flags_as_dict(event):
    event.feature_flags["show_schedule"] = True
    event.save(update_fields=["feature_flags"])

    form = EventForm(
        data={
            "id": event.id,
            "domain": event.domain or "",
            "locale": event.locale,
            "timezone": event.timezone,
            "feature_flags": ["jitsi"],
            "external_auth_url": event.external_auth_url or "",
        },
        instance=event,
    )

    assert form.is_valid(), form.errors
    updated = form.save()

    assert isinstance(updated.feature_flags, dict)
    assert updated.feature_flags["jitsi"] is True
    assert updated.feature_flags["show_schedule"] is True


@pytest.mark.django_db
def test_event_form_repairs_list_feature_flags(event):
    event.feature_flags = ["jitsi"]
    event.save(update_fields=["feature_flags"])

    form = EventForm(
        data={
            "id": event.id,
            "domain": event.domain or "",
            "locale": event.locale,
            "timezone": event.timezone,
            "feature_flags": ["jitsi"],
            "external_auth_url": event.external_auth_url or "",
        },
        instance=event,
    )

    assert form.is_valid(), form.errors
    updated = form.save()

    assert isinstance(updated.feature_flags, dict)
    assert updated.feature_flags["jitsi"] is True
