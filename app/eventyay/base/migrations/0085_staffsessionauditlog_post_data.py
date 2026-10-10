from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0084_voucher_all_addons_bundles_included'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffsessionauditlog',
            name='post_data',
            field=models.TextField(blank=True, null=True),
        ),
    ]
