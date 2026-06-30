from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0033_device_limit_to_checkin_lists'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='security_profile',
            field=models.CharField(
                blank=False,
                choices=[
                    ('full', 'Full device access (reading and changing orders and gift cards, reading of products and settings)'),
                    ('eventyay_checkin', 'Check-In Staff'),
                    ('eventyay_checkin_online_kiosk', 'Badge Station (kiosk)'),
                ],
                default='full',
                max_length=190,
                null=True,
            ),
        ),
    ]
