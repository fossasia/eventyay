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
