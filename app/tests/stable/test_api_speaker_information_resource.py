import json

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django_scopes import scope

from eventyay.api.serializers import speaker_information as speaker_information_serializers


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def team_token(team):
    # The upload endpoint only accepts team tokens, and an uploaded file can only be
    # used by the same client that uploaded it, so the tests use this token for both.
    return team.tokens.create(name='testtoken')


def upload_file(client, team_token, content, name):
    response = client.post(
        '/api/v1/upload',
        data={'file': ContentFile(content, name=name)},
        headers={'Authorization': f'Token {team_token.token}'},
    )
    assert response.status_code == 201, response.content
    return response.json()['id']


def patch_resource(client, team_token, event, speaker_info, file_id):
    return client.patch(
        event.api_urls.speaker_information + f'{speaker_info.pk}/',
        follow=True,
        data=json.dumps({'resource': file_id}),
        headers={
            'Authorization': f'Token {team_token.token}',
            'Content-Type': 'application/json',
        },
    )


@pytest.mark.django_db
def test_orga_can_replace_speaker_information_resource(
    client, event, team_token, media_root, allow_all_entitlements, django_capture_on_commit_callbacks
):
    with scope(event=event):
        speaker_info = event.information.create(
            title='Test Info', text='This is some test information', target_group='accepted'
        )
        speaker_info.resource.save('old.pdf', ContentFile(b'%PDF-1.4 old'))
        old_name = speaker_info.resource.name
    assert default_storage.exists(old_name)

    file_id = upload_file(client, team_token, b'%PDF-1.4 new', 'new.pdf')

    with django_capture_on_commit_callbacks(execute=True):
        response = patch_resource(client, team_token, event, speaker_info, file_id)
        assert response.status_code == 200, response.text
        # The old file is only deleted once the transaction commits.
        assert default_storage.exists(old_name)

    with scope(event=event):
        speaker_info.refresh_from_db()
        new_name = speaker_info.resource.name
    assert new_name != old_name
    assert default_storage.exists(new_name)
    assert not default_storage.exists(old_name)
    with default_storage.open(new_name) as new_file:
        assert new_file.read() == b'%PDF-1.4 new'


@pytest.mark.django_db
def test_orga_can_add_resource_to_speaker_information_without_one(
    client, event, team_token, media_root, monkeypatch, allow_all_entitlements, django_capture_on_commit_callbacks
):
    deleted_names = []
    monkeypatch.setattr(speaker_information_serializers, 'delete_stored_file', deleted_names.append)
    with scope(event=event):
        speaker_info = event.information.create(
            title='Test Info', text='This is some test information', target_group='accepted'
        )
    assert not speaker_info.resource

    file_id = upload_file(client, team_token, b'%PDF-1.4 first', 'first.pdf')

    with django_capture_on_commit_callbacks(execute=True):
        response = patch_resource(client, team_token, event, speaker_info, file_id)
    assert response.status_code == 200, response.text
    assert deleted_names == []

    with scope(event=event):
        speaker_info.refresh_from_db()
        new_name = speaker_info.resource.name
    assert new_name
    with default_storage.open(new_name) as new_file:
        assert new_file.read() == b'%PDF-1.4 first'


@pytest.mark.django_db
def test_replacing_speaker_information_resource_keeps_file_used_by_another_entry(
    client, event, team_token, media_root, allow_all_entitlements, django_capture_on_commit_callbacks
):
    with scope(event=event):
        first = event.information.create(title='First', text='First entry', target_group='accepted')
        first.resource.save('shared.pdf', ContentFile(b'%PDF-1.4 shared'))
        shared_name = first.resource.name
        second = event.information.create(title='Second', text='Second entry', target_group='accepted')
        second.resource = shared_name
        second.save()

    file_id = upload_file(client, team_token, b'%PDF-1.4 new', 'new.pdf')

    with django_capture_on_commit_callbacks(execute=True):
        response = patch_resource(client, team_token, event, first, file_id)
    assert response.status_code == 200, response.text

    with scope(event=event):
        first.refresh_from_db()
        second.refresh_from_db()
    assert first.resource.name != shared_name
    assert second.resource.name == shared_name
    # The second entry still uses the old file, so it must not be deleted.
    assert default_storage.exists(shared_name)
