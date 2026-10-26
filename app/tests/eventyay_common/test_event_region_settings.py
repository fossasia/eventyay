import re
from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import Event
from eventyay.eventyay_common.forms.event import EventCommonSettingsForm


@pytest.mark.django_db
@scopes_disabled()
def test_event_settings_form_region_and_timezone_are_searchable(organizer):
    now = timezone.now()
    event = Event.objects.create(
        organizer=organizer,
        name='Searchable Region Event',
        slug='searchable-region-event',
        date_from=now + timedelta(days=10),
        date_to=now + timedelta(days=11),
        currency='USD',
        locale='en',
    )

    form = EventCommonSettingsForm(obj=event)
    for field_name in ('timezone', 'region'):
        attrs = form.fields[field_name].widget.attrs
        assert 'data-searchable-select' in attrs
        assert attrs['data-search-placeholder'] == 'Search'
        assert attrs['data-empty-text'] == 'No results'
        assert attrs['class'] == 'form-control'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_event_settings_page_renders_searchable_region_selects(organizer_client, event):
    url = reverse('eventyay_common:event.update', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = organizer_client.get(url)
    assert response.status_code == 200

    content = response.content.decode('utf-8')
    assert 'common/css/searchable-select.css' in content
    assert 'common/js/searchable-select.js' in content

    # Check timezone select in Basics tab (rendered with Region label)
    timezone_match = re.search(r'<select[^>]*name="settings-timezone"[^>]*>', content)
    assert timezone_match is not None
    assert 'data-searchable-select' in timezone_match.group(0)

    # Check region country select in Localization tab
    region_match = re.search(r'<select[^>]*name="settings-region"[^>]*>', content)
    assert region_match is not None
    assert 'data-searchable-select' in region_match.group(0)
