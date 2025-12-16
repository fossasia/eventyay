# Generated manually on 2025-12-16

from django.db import migrations


def set_existing_events_login_not_required(apps, schema_editor):
    """
    Set require_registered_account_for_tickets to False for all existing events.
    New events will get the default value of True from default_setting.py.
    """
    Event = apps.get_model('base', 'Event')
    
    # Update all existing events to have login NOT required (to preserve current behavior)
    for event in Event.objects.all():
        event.settings.set('require_registered_account_for_tickets', False)


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - set all events back to True (the default).
    """
    Event = apps.get_model('base', 'Event')
    
    for event in Event.objects.all():
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
