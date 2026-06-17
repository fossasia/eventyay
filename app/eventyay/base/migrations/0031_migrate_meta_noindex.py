# Generated manually for data migration

from django.db import migrations

def migrate_meta_noindex(apps, schema_editor):
    Event = apps.get_model('base', 'Event')
    Event_SettingsStore = apps.get_model('base', 'Event_SettingsStore')
    
    for event in Event.objects.all():
        if event.display_settings and event.display_settings.get('meta_noindex') is True:
            # Hierarkey stores boolean True as string 'True'
            Event_SettingsStore.objects.update_or_create(
                object=event,
                key='meta_noindex',
                defaults={'value': 'True'}
            )

class Migration(migrations.Migration):

    dependencies = [
        ('base', '0030_room_is_unscheduled_team_polls_questions'),
    ]

    operations = [
        migrations.RunPython(migrate_meta_noindex, reverse_code=migrations.RunPython.noop),
    ]
