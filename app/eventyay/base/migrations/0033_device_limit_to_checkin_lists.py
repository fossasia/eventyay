from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0032_checkinlist_exit_and_limits'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='limit_to_checkin_lists',
            field=models.ManyToManyField(
                blank=True,
                to='base.checkinlist',
                verbose_name='Limit to check-in lists',
            ),
        ),
    ]
