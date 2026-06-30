from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0035_user_is_spam'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='limit_checkin_lists',
            field=models.ManyToManyField(
                blank=True,
                to='base.checkinlist',
                verbose_name='Limit to check-in lists',
            ),
        ),
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
        migrations.AddField(
            model_name='product',
            name='admission_validity_mode',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'No check-in time restriction'),
                    ('fixed', 'Fixed start and end'),
                    ('subevent', 'Valid during assigned event date'),
                    ('event', 'Valid during entire event'),
                ],
                default='',
                help_text='How check-in validity is determined for tickets of this product.',
                max_length=20,
                verbose_name='Admission validity mode',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='admission_valid_from',
            field=models.DateTimeField(
                blank=True,
                help_text='Used when admission validity mode is "Fixed start and end".',
                null=True,
                verbose_name='Admission valid from',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='admission_valid_until',
            field=models.DateTimeField(
                blank=True,
                help_text='Used when admission validity mode is "Fixed start and end".',
                null=True,
                verbose_name='Admission valid until',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='admission_valid_from_offset_minutes',
            field=models.IntegerField(
                blank=True,
                help_text=(
                    'For event or date-based validity: minutes after the window start when check-in becomes allowed.'
                ),
                null=True,
                verbose_name='Admission valid from offset (minutes)',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='admission_valid_until_offset_minutes',
            field=models.IntegerField(
                blank=True,
                help_text=(
                    'For event or date-based validity: minutes after the window start when check-in stops. '
                    'Leave empty to use the window end.'
                ),
                null=True,
                verbose_name='Admission valid until offset (minutes)',
            ),
        ),
        migrations.AddField(
            model_name='productvariation',
            name='admission_validity_mode',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'No check-in time restriction'),
                    ('fixed', 'Fixed start and end'),
                    ('subevent', 'Valid during assigned event date'),
                    ('event', 'Valid during entire event'),
                ],
                default='',
                help_text='Overrides the product admission validity mode when set.',
                max_length=20,
                verbose_name='Admission validity mode',
            ),
        ),
        migrations.AddField(
            model_name='productvariation',
            name='admission_valid_from',
            field=models.DateTimeField(
                blank=True,
                help_text='Used when admission validity mode is "Fixed start and end".',
                null=True,
                verbose_name='Admission valid from',
            ),
        ),
        migrations.AddField(
            model_name='productvariation',
            name='admission_valid_until',
            field=models.DateTimeField(
                blank=True,
                help_text='Used when admission validity mode is "Fixed start and end".',
                null=True,
                verbose_name='Admission valid until',
            ),
        ),
        migrations.AddField(
            model_name='productvariation',
            name='admission_valid_from_offset_minutes',
            field=models.IntegerField(
                blank=True,
                help_text=(
                    'For event or date-based validity: minutes after the window start when check-in becomes allowed.'
                ),
                null=True,
                verbose_name='Admission valid from offset (minutes)',
            ),
        ),
        migrations.AddField(
            model_name='productvariation',
            name='admission_valid_until_offset_minutes',
            field=models.IntegerField(
                blank=True,
                help_text=(
                    'For event or date-based validity: minutes after the window start when check-in stops. '
                    'Leave empty to use the window end.'
                ),
                null=True,
                verbose_name='Admission valid until offset (minutes)',
            ),
        ),
        migrations.AddField(
            model_name='orderposition',
            name='admission_valid_from',
            field=models.DateTimeField(
                blank=True,
                help_text='Check-in allowed from this time for this ticket (copied from the product when the order was placed).',
                null=True,
                verbose_name='Issued admission valid from',
            ),
        ),
        migrations.AddField(
            model_name='orderposition',
            name='admission_valid_until',
            field=models.DateTimeField(
                blank=True,
                help_text='Check-in allowed until this time for this ticket (copied from the product when the order was placed).',
                null=True,
                verbose_name='Issued admission valid until',
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
        migrations.AlterField(
            model_name='device',
            name='security_profile',
            field=models.CharField(
                choices=[
                    ('full', 'Full device access'),
                    ('eventyay_checkin', 'Check-In Staff'),
                    ('eventyay_checkin_online_kiosk', 'Badge Station (kiosk)'),
                ],
                default='full',
                max_length=190,
                null=True,
            ),
        ),
    ]
