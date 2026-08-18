from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0053_jitsiserver'),
    ]

    operations = [
        migrations.CreateModel(
            name='GlobalPluginConfig',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'module',
                    models.CharField(
                        help_text='The Python module path of the plugin.',
                        max_length=255,
                        unique=True,
                        verbose_name='Plugin module',
                    ),
                ),
                (
                    'is_active',
                    models.BooleanField(
                        default=True,
                        help_text='Controls whether the plugin is available on the platform at all.',
                        verbose_name='Active',
                    ),
                ),
                (
                    'enable_by_default',
                    models.BooleanField(
                        default=False,
                        help_text='Controls whether the plugin is automatically enabled for new events.',
                        verbose_name='Enable by default',
                    ),
                ),
                (
                    'show_in_organizer_list',
                    models.BooleanField(
                        default=True,
                        help_text='Controls whether the plugin appears in the organiser/event plugin settings.',
                        verbose_name='Show in organizer plugin list',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Global plugin configuration',
                'verbose_name_plural': 'Global plugin configurations',
                'ordering': ('module',),
            },
        ),
    ]
