from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import CachedFile


IMPORT_VIEWS = [
    ('settings.import_export.speakers_import_process', 'speaker', 'speaker_import.csv'),
    ('settings.import_export.submissions_import_process', 'session', 'session_import.csv'),
]


@pytest.mark.django_db
@pytest.mark.parametrize(('url_name', 'import_target', 'filename'), IMPORT_VIEWS)
def test_import_mapping_page_with_expired_file_redirects(organizer_client, event, url_name, import_target, filename):
    kwargs = {'organizer': event.organizer.slug, 'event': event.slug}
    # Create the cached upload like ImportExportSettings.handle_import does.
    cached_file = CachedFile.objects.create(
        expires=now() + timedelta(days=1),
        date=now(),
        filename=filename,
        type='text/csv',
        web_download=False,
        session_key=organizer_client.session.session_key,
    )
    cached_file.file.save(filename, ContentFile(b'name,email\nFake Speaker,fake.speaker@example.com\n'))
    mapping_url = reverse(f'orga:{url_name}', kwargs={**kwargs, 'file': cached_file.id})
    # clean_cached_files deletes the upload once it has expired.
    cached_file.delete()

    response = organizer_client.get(mapping_url)

    import_page = reverse('orga:settings.import_export', kwargs=kwargs)
    assert response.status_code == 302
    assert response.url == f'{import_page}?import_target={import_target}#tab-import'
    assert 'missing or expired' in ' '.join(str(message) for message in get_messages(response.wsgi_request))
