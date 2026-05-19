from django.db import migrations, models


def remove_placeholder_emails(apps, schema_editor):
    Event = apps.get_model('base', 'Event')
    Event.objects.filter(email='org@mail.com').update(email=None)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0024_remove_event_featured_sessions_text'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='email',
            field=models.EmailField(
                blank=True,
                help_text=(
                    'Optional organizer contact email. '
                    'When the platform sender is used, this address will be used as the Reply-To header. '
                    'If left empty, no Reply-To is added automatically and replies go to the platform sender.'
                ),
                max_length=254,
                null=True,
                verbose_name='Organizer email address',
            ),
        ),
        migrations.RunPython(remove_placeholder_emails, migrations.RunPython.noop),
    ]
