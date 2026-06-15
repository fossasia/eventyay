from django.db import migrations, models


class Migration(migrations.Migration):
    
    dependencies = [
        ('base', '0030_room_is_unscheduled_team_polls_questions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='private_testmode',
            field=models.BooleanField(default=False),
        ),
    ]
