from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0031_migrate_meta_noindex'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkinlist',
            name='allow_exit',
            field=models.BooleanField(
                default=False,
                help_text='If this is disabled, exit scans will be rejected.',
                verbose_name='Allow exit scans',
            ),
        ),
        migrations.AddField(
            model_name='checkinlist',
            name='limit_one_checkin_per_day',
            field=models.BooleanField(
                default=False,
                help_text='If this is enabled, every ticket can only be scanned once per calendar day.',
                verbose_name='Limit to one entry per day',
            ),
        ),
        migrations.AddField(
            model_name='checkinlist',
            name='limit_one_checkin_per_gate',
            field=models.BooleanField(
                default=False,
                help_text='If this is enabled, every ticket can only be scanned once per gate.',
                verbose_name='Limit to one entry per gate',
            ),
        ),
    ]
