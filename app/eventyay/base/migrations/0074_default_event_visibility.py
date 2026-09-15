# Data migration for #5551.
#
# The "Show in search results and lists" (is_public) and "Ask search engines not to
# index" (meta_noindex) toggles were removed from the event settings UI, and events are
# now public and indexed by default. Existing events that had been hidden through those
# toggles would otherwise be stranded — invisible in lists/search with no UI to re-enable
# them — so bring them back to the default public/indexed state.
#
# Meetups deliberately use these fields for their own privacy control (identified by the
# ``event_type=meetup`` setting and driven by the separate ``privacy_type`` field), so
# they are left untouched.
from django.db import migrations


def make_events_public_and_indexed(apps, schema_editor):
    Event = apps.get_model('base', 'Event')
    Event_SettingsStore = apps.get_model('base', 'Event_SettingsStore')

    meetup_ids = list(
        Event_SettingsStore.objects.filter(key='event_type', value='meetup').values_list(
            'object_id', flat=True
        )
    )

    # Make previously hidden events show up in lists/search again.
    Event.objects.filter(is_public=False).exclude(pk__in=meetup_ids).update(is_public=True)

    # Drop any stored meta_noindex override so events fall back to the indexed default.
    Event_SettingsStore.objects.filter(key='meta_noindex').exclude(
        object_id__in=meetup_ids
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0073_loungemeshaccesstoken_loungemeshserver_and_more'),
    ]

    operations = [
        migrations.RunPython(
            make_events_public_and_indexed,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
