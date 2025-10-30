from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0005_alter_logentry_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_wikimedia_user',
            field=models.BooleanField(default=False, verbose_name='Is Wikimedia user'),
        ),
        migrations.AlterField(
            model_name='user',
            name='wikimedia_username',
            field=models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name='Wikimedia username'),
        ),
    ]
