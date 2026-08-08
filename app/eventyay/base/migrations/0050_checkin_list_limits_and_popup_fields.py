import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0049_alter_talkquestion_variant_add_video'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkinlist',
            name='limit_one_checkin_per_day',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Each ticket can only be checked in once per calendar day on this list, '
                    'even after an exit scan. Disable this to allow same-day re-entry after checkout.'
                ),
                verbose_name='Limit to one check-in per day',
            ),
        ),
        migrations.AddField(
            model_name='checkinlist',
            name='limit_one_checkin_per_gate',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Each ticket can only be checked in once per gate on this list. '
                    'When combined with the per-day limit, the restriction is one entry per gate per day.'
                ),
                verbose_name='Limit to one check-in per gate',
            ),
        ),
        migrations.AddField(
            model_name='checkinlist',
            name='display_popup_fields',
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=190),
                blank=True,
                default=list,
                help_text='Additional attendee registration fields to display on the check-in success pop-up screen.',
                size=None,
                verbose_name='Check-in app display fields',
            ),
        ),
        migrations.AlterField(
            model_name='checkinlist',
            name='gates',
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    'Assign gates to devices for automatic configuration. When per-gate check-in limits are '
                    'enabled, the device gate is used to enforce them.'
                ),
                to='base.gate',
                verbose_name='Gates',
            ),
        ),
    ]
