from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0093_team_can_view_event_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='productvariation',
            name='available_from',
            field=models.DateTimeField(
                blank=True,
                help_text='This variation will not be sold before the given date.',
                null=True,
                verbose_name='Available from',
            ),
        ),
        migrations.AddField(
            model_name='productvariation',
            name='available_until',
            field=models.DateTimeField(
                blank=True,
                help_text='This variation will not be sold after the given date.',
                null=True,
                verbose_name='Available until',
            ),
        ),
    ]
