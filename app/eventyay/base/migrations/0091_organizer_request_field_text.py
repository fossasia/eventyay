from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0090_team_invite_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizerrequestfieldsetting',
            name='label',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='organizerrequestfieldsetting',
            name='help_text',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
