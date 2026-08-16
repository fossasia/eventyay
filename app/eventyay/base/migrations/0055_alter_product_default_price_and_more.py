# Generated manually for price validator

from decimal import Decimal
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0054_team_teamshifts_permissions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='default_price',
            field=models.DecimalField(
                decimal_places=2,
                help_text=(
                    'If this product has multiple variations, you can set different prices for each of the '
                    'variations. If a variation does not have a special price or if you do not have variations, '
                    'this price will be used.'
                ),
                max_digits=7,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
                verbose_name='Default price',
            ),
        ),
        migrations.AlterField(
            model_name='productvariation',
            name='default_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=7,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
                verbose_name='Default price',
            ),
        ),
    ]
