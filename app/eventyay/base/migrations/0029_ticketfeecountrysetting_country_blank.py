import eventyay.helpers.countries
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0028_ticketfeecountrysetting'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticketfeecountrysetting',
            name='country',
            field=eventyay.helpers.countries.FastCountryField(
                blank=True,
                countries=eventyay.helpers.countries.CachedCountries,
                max_length=2,
                verbose_name='Country',
            ),
        ),
    ]
