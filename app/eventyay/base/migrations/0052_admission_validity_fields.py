from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0051_consolidate_video_team_permissions'),
    ]

    operations = [
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
                choices=[
                    ('inherit', 'Same as product'),
                    ('', 'No check-in time restriction'),
                    ('fixed', 'Fixed start and end'),
                    ('subevent', 'Valid during assigned event date'),
                    ('event', 'Valid during entire event'),
                ],
                default='inherit',
                help_text=(
                    'Use "Same as product" to inherit the product mode and overlay only the '
                    'variation fields you set. Choose "No check-in time restriction" to explicitly '
                    'clear a product-level restriction for this variation.'
                ),
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
                help_text=(
                    'Check-in allowed from this time for this ticket (snapshotted from the product '
                    'when the order was placed). If both issued fields are empty, current product '
                    'admission settings are used.'
                ),
                null=True,
                verbose_name='Issued admission valid from',
            ),
        ),
        migrations.AddField(
            model_name='orderposition',
            name='admission_valid_until',
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    'Check-in allowed until this time for this ticket (snapshotted from the product '
                    'when the order was placed). If both issued fields are empty, current product '
                    'admission settings are used.'
                ),
                null=True,
                verbose_name='Issued admission valid until',
            ),
        ),
    ]
