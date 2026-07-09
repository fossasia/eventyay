from django.db import migrations

def remove_sendmail_from_plugins(apps, schema_editor):
    Event = apps.get_model('base', 'Event')
    for event in Event.objects.all():
        if event.plugins:
            plugins = event.plugins.split(',')
            if 'eventyay.plugins.sendmail' in plugins:
                plugins.remove('eventyay.plugins.sendmail')
                event.plugins = ','.join(plugins)
                event.save(update_fields=['plugins'])

class Migration(migrations.Migration):

    dependencies = [
        ('base', '0041_make_event_email_optional'),
    ]

    operations = [
        migrations.RunPython(remove_sendmail_from_plugins, reverse_code=migrations.RunPython.noop),
    ]
