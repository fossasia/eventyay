from django.db import migrations, models


class Migration(migrations.Migration):
    
    dependencies = [
        ('base', '0032_submission_etherpad_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='private_testmode',
            field=models.BooleanField(default=False),
        ),
    ]
