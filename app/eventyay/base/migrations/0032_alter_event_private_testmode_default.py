from django.db import migrations, models


class Migration(migrations.Migration):
    
    dependencies = [
        ('base', '0031_migrate_meta_noindex'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='private_testmode',
            field=models.BooleanField(default=False),
        ),
    ]
