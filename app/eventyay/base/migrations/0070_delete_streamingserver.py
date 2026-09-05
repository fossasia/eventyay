from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0069_taxrule_tax_rate_bounds'),
    ]

    operations = [
        migrations.DeleteModel(
            name='StreamingServer',
        ),
    ]
