from django.db import migrations, models


def set_initial_visibility(apps, schema_editor):
    Room = apps.get_model("base", "Room")
    batch = []
    for room in Room.objects.all().iterator():
        has_modules = bool(room.module_config)
        room.setup_complete = has_modules
        room.sidebar_hidden = not has_modules
        batch.append(room)
    if batch:
        Room.objects.bulk_update(
            batch,
            fields=[
                "setup_complete",
                "sidebar_hidden",
            ],
        )


def noop_reverse(apps, schema_editor):
    # We deliberately keep any user input and do not try to restore previous state.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="hidden",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="room",
            name="setup_complete",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="room",
            name="sidebar_hidden",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(set_initial_visibility, noop_reverse),
    ]

