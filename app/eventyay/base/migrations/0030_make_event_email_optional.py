from django.db import migrations, models


def remove_placeholder_emails(apps, schema_editor):
    Event = apps.get_model('base', 'Event')
    Event.objects.filter(email='org@mail.com').update(email=None)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0029_organizerfollower'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='email',
            field=models.EmailField(
                blank=True,
                help_text=(
                    'Enter an organizer email address for event-related emails. '
                    'If set, this address will be used as the Reply-To when the platform sender address is used. '
                    'If left empty, no Reply-To will be added automatically and replies will go to the sender address (platform default if not customized).'
                ),
                max_length=254,
                null=True,
                verbose_name='Organizer email address',
            ),
        ),
        migrations.RunPython(remove_placeholder_emails, migrations.RunPython.noop),
    ]
