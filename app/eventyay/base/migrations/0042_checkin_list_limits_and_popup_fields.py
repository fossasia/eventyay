from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0041_make_event_email_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkinlist',
            name='limit_one_checkin_per_day',
            field=models.BooleanField(
                default=True,
                help_text='Each ticket can only be checked in once per calendar day on this list.',
                verbose_name='Limit to one check-in per day',
            ),
        ),
        migrations.AddField(
            model_name='checkinlist',
            name='limit_one_checkin_per_gate',
            field=models.BooleanField(
                default=True,
                help_text='Each ticket can only be checked in once per gate on this list.',
                verbose_name='Limit to one check-in per gate',
            ),
        ),
        migrations.AddField(
            model_name='checkinlist',
            name='display_popup_fields',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Additional attendee registration fields to display on the check-in success pop-up screen.',
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
