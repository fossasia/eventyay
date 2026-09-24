import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from eventyay.base.models import (
    BBBServer,
    JanusServer,
    JitsiServer,
    LoungeMeshServer,
    TurnServer,
)
from eventyay.base.models.auth import StaffSession
from eventyay.base.models.log import LogEntry


SERVERS = [
    (BBBServer, {'url': 'https://bbb.example.com/', 'secret': 's'}, 'bbbserver'),
    (JanusServer, {'url': 'https://janus.example.com/', 'room_create_key': 'k'}, 'janusserver'),
    (JitsiServer, {'url': 'https://jitsi.example.com/', 'app_id': 'a', 'app_secret': 's'}, 'jitsiserver'),
    (TurnServer, {'hostname': 'turn.example.com', 'auth_secret': 's'}, 'turnserver'),
    (LoungeMeshServer, {'url': 'https://mesh.example.com/'}, 'loungemeshserver'),
]


@pytest.mark.django_db
@pytest.mark.parametrize('model, fields, name', SERVERS, ids=[s[2] for s in SERVERS])
def test_deleting_a_video_server_writes_an_audit_log_entry(staff_client, staff_user, model, fields, name):
    server = model.objects.create(**fields)
    StaffSession.objects.create(user=staff_user, session_key=staff_client.session.session_key)

    response = staff_client.post(reverse(f'eventyay_admin:video_admin:{name}.delete', kwargs={'pk': server.pk}))

    assert response.status_code == 302
    assert not model.objects.filter(pk=server.pk).exists()
    entry = LogEntry.objects.get(action_type=f'{name}.deleted')
    assert entry.user == staff_user
    assert entry.content_type == ContentType.objects.get_for_model(model)
    # object_id is a JSONField, so a UUID primary key comes back as a string
    assert str(entry.object_id) == str(server.pk)
