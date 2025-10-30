from django.db import migrations

def enable_all_components(apps, schema_editor):
    Event = apps.get_model("base", "Event")
    Event.objects.all().update(has_subevents=True, is_video_creation=True)

class Migration(migrations.Migration):

    dependencies = [
        ('base', '0005_alter_logentry_data'), # Update this if you have a newer migration
    ]

    operations = [
        migrations.RunPython(enable_all_components),
    ]
