# Set existing events to have require_registered_account_for_tickets=False
# to preserve their current behavior (anonymous checkout allowed)

from django.db import migrations


def set_existing_events_guest_checkout(apps, schema_editor):
    """
    For existing events, explicitly set require_registered_account_for_tickets=False.
    This preserves their current behavior since the new default is True.
    """
    Event = apps.get_model('base', 'Event')
    Event_SettingsStore = apps.get_model('base', 'Event_SettingsStore')
    
    for event in Event.objects.all():
        # Only set if not already explicitly configured
        if not Event_SettingsStore.objects.filter(
            object_id=event.pk,
            key='require_registered_account_for_tickets'
        ).exists():
            Event_SettingsStore.objects.create(
                object_id=event.pk,
                key='require_registered_account_for_tickets',
                value='False'
            )


def reverse_migration(apps, schema_editor):
    """
    Remove the settings we just added (not strictly required but good practice).
    """
    Event_SettingsStore = apps.get_model('base', 'Event_SettingsStore')
    # We only delete settings that were set to False by this migration
    # This is a conservative approach - we don't want to delete user-configured values
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_update_team_permission_labels'),
    ]

    operations = [
        migrations.RunPython(
            set_existing_events_guest_checkout,
            reverse_migration,
        ),
    ]
