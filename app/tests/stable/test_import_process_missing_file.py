import uuid

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('url_name', 'import_target'),
    [
        ('orga:settings.import_export.speakers_import_process', 'speaker'),
        ('orga:settings.import_export.submissions_import_process', 'session'),
    ],
)
def test_import_process_redirects_when_file_is_gone(organizer_client, event, url_name, import_target):
    url = reverse(url_name, kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'file': uuid.uuid4()})

    response = organizer_client.get(url)

    assert response.status_code == 302
    assert response.url.startswith(event.orga_urls.import_export_settings)
    assert f'import_target={import_target}' in response.url
    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        'The uploaded CSV file is missing or expired. Please upload it again.'
    ]
