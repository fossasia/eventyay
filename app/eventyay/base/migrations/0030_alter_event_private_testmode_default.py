from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0029_organizerfollower'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='private_testmode',
            field=models.BooleanField(default=False),
        ),
    ]
