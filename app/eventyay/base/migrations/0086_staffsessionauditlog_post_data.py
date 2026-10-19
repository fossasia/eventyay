from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0085_user_last_accessed_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffsessionauditlog',
            name='post_data',
            field=models.TextField(blank=True, null=True),
        ),
    ]
