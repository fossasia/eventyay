import pytest
from django.core.files.base import ContentFile


@pytest.mark.django_db
def test_upload_file(token_client):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile('file.pdf', 'invalid pdf content'),
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="file.pdf"',
    )
    assert r.status_code == 201
    assert r.data['id'].startswith('file:')


@pytest.mark.django_db
def test_upload_file_extension_mismatch(token_client):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': 'application/pdf',
            'file': ContentFile('file.png', 'invalid pdf content'),
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION='attachment; filename="file.png"',
    )
    assert r.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    'filename,media_type',
    [
        ('file.webp', 'image/webp'),
        ('file.WEBP', 'image/webp'),
        ('file.WebP', 'image/webp'),
        ('file.PNG', 'image/png'),
        ('file.JPG', 'image/jpeg'),
    ],
)
def test_upload_file_case_insensitive_extension(
    token_client, filename, media_type
):
    r = token_client.post(
        '/api/v1/upload',
        data={
            'media_type': media_type,
            'file': ContentFile(filename, 'fake image content'),
        },
        format='upload',
        HTTP_CONTENT_DISPOSITION=f'attachment; filename="{filename}"',
    )
    assert r.status_code == 201
    assert r.data['id'].startswith('file:')
