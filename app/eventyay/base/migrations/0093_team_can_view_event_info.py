from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0092_speaker_vouchers'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='can_view_event_info',
            field=models.BooleanField(
                default=False,
                help_text='For website and other integrations that only display event information',
                verbose_name='Read-only access to event information',
            ),
        ),
    ]
