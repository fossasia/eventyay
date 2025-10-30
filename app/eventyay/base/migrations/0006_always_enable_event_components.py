from django.db import migrations

def enable_all_components(apps, schema_editor):
    Event = apps.get_model("base", "Event")
    Event.objects.all().update(has_subevents=True, is_video_creation=True)


def disable_all_components(apps, schema_editor):
    # Reverse operation: restore both flags to False for all events
    Event = apps.get_model("base", "Event")
    Event.objects.all().update(has_subevents=False, is_video_creation=False)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0005_alter_logentry_data'),  # Update this if you have a newer migration
    ]

    operations = [
        migrations.RunPython(enable_all_components, disable_all_components),
    ]
