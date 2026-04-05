import json

from django.db import migrations


def _trait_grants_as_dict(raw):
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _viewer_is_open_list(trait_grants):
    if 'viewer' not in trait_grants:
        return False
    v = trait_grants['viewer']
    return isinstance(v, list) and len(v) == 0


def ensure_participant_for_open_viewer_rooms(apps, schema_editor):
    """
    Rooms with "viewer": [] but no "participant" in trait_grants cannot grant
    ROOM_CHAT_JOIN to regular users. Add participant: [] for those open-viewer rooms.
    """
    Room = apps.get_model('base', 'Room')
    for room in Room.objects.all().iterator(chunk_size=500):
        trait_grants = _trait_grants_as_dict(room.trait_grants)
        if (
            _viewer_is_open_list(trait_grants)
            and 'participant' not in trait_grants
        ):
            updated = dict(trait_grants)
            updated['participant'] = []
            room.trait_grants = updated
            room.save(update_fields=['trait_grants'])


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0022_alter_event_currency_alter_giftcard_currency'),
    ]

    operations = [
        migrations.RunPython(
            ensure_participant_for_open_viewer_rooms,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
