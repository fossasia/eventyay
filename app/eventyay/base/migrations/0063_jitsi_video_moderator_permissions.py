from django.db import migrations


JITSI_VIDEO_MODERATOR_PERMISSIONS = [
    'room:jitsi.join',
    'room:jitsi.moderate',
]


def add_jitsi_permissions_to_video_moderator(apps, schema_editor):
    Event = apps.get_model('base', 'Event')
    models_to_update = [Event]
    try:
        models_to_update.append(apps.get_model('base', 'World'))
    except LookupError:
        pass

    for model in models_to_update:
        for obj in model.objects.exclude(roles__isnull=True).iterator():
            roles = obj.roles or {}
            role_permissions = roles.get('video_moderator')
            if role_permissions is None:
                continue

            changed = False
            for permission in JITSI_VIDEO_MODERATOR_PERMISSIONS:
                if permission not in role_permissions:
                    role_permissions.append(permission)
                    changed = True

            if changed:
                obj.save(update_fields=['roles'])


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0062_attendee_feedback_redesign'),
    ]

    operations = [
        migrations.RunPython(
            add_jitsi_permissions_to_video_moderator,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
