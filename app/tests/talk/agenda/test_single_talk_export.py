import json

import pytest
from lxml import etree


@pytest.mark.django_db
def test_single_talk_json_export(slot, client):
    response = client.get(slot.submission.urls.export_json, follow=True)
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["code"] == slot.submission.code
    assert "talks" in content
    assert len(content["talks"]) >= 1
    talk = content["talks"][0]
    assert talk["code"] == slot.submission.code
    assert "start" in talk
    assert "room" in talk
    assert "persons" in talk


@pytest.mark.django_db
def test_single_talk_xml_export(slot, client):
    response = client.get(slot.submission.urls.export_xml, follow=True)
    assert response.status_code == 200
    assert "xml" in response["Content-Type"]

    parser = etree.XMLParser()
    tree = etree.fromstring(response.content, parser)
    assert tree.tag == "schedule"
    events = tree.findall(".//event")
    assert len(events) == 1
    assert events[0].find("title").text == slot.submission.title


@pytest.mark.django_db
def test_single_talk_xcal_export(slot, client):
    response = client.get(slot.submission.urls.export_xcal, follow=True)
    assert response.status_code == 200
    assert "xml" in response["Content-Type"]

    parser = etree.XMLParser()
    etree.fromstring(response.content, parser)


@pytest.mark.django_db
def test_single_talk_google_calendar_redirect(slot, client):
    response = client.get(
        slot.submission.urls.export_google_calendar, follow=False
    )
    assert response.status_code == 302
    location = response["Location"]
    assert "calendar.google.com" in location
    assert slot.submission.title in location or "text=" in location


@pytest.mark.django_db
def test_single_talk_webcal_redirect(slot, client):
    response = client.get(
        slot.submission.urls.export_webcal, follow=False
    )
    assert response.status_code == 302
    location = response["Location"]
    assert location.startswith("webcal://")
    assert ".ics" in location


@pytest.mark.django_db
def test_single_talk_export_nonexistent(slot, client):
    url = slot.submission.urls.export_json.replace(
        slot.submission.code, "NONEXIST"
    )
    response = client.get(url, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_single_talk_export_nonpublic_event(slot, client):
    slot.submission.event.is_public = False
    slot.submission.event.save()

    response = client.get(slot.submission.urls.export_json, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_single_talk_export_invalid_format(slot, client):
    from django.urls import reverse

    url = reverse(
        "agenda:talk-export",
        kwargs={
            "event": slot.submission.event.slug,
            "slug": slot.submission.code,
            "format": "invalid",
        },
    )
    response = client.get(url, follow=True)
    assert response.status_code == 404
