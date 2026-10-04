from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0083_admin_mail_i18n_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffsessionauditlog',
            name='post_data',
            field=models.TextField(blank=True, null=True),
        ),
    ]
