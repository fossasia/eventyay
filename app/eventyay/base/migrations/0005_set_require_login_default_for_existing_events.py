from django.db import migrations


def set_existing_events_login_not_required(apps, schema_editor):
    """
    Set require_registered_account_for_tickets to False for all existing events.
    New events will get the default value of True from default_setting.py.
    """
    Event = apps.get_model('base', 'Event')
    
    # Use iterator() to stream results for better performance with large datasets
    for event in Event.objects.iterator():
        event.settings.set('require_registered_account_for_tickets', False)


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - set all events back to True (the default).
    """
    Event = apps.get_model('base', 'Event')
    
    # Use iterator() for consistency with forward migration
    for event in Event.objects.iterator():
        event.settings.set('require_registered_account_for_tickets', True)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_update_team_permission_labels'),
    ]

    operations = [
        migrations.RunPython(
            set_existing_events_login_not_required,
            reverse_migration
        ),
    ]
